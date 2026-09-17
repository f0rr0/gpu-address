"""Explicit PyTorch training loop and checkpoint provenance."""

import argparse
import json
import math
import platform
import random
import shutil
import tempfile
import time
from collections import Counter
from contextlib import ExitStack
from pathlib import Path

import numpy as np
import torch
from torch import nn

from .data import batch, case_variant, load, read_batch, spool, structural_variant
from .evaluate import evaluate
from .expand import file_sha256
from .export import serialize
from .model import ARCHITECTURE, Tagger
from .paths import ROOT, SOURCE
from .schema import LABELS

ROBUST_PANELS = {
    "clean": "dev.jsonl.gz",
    "old-us": "dev-old-us.jsonl.gz",
    "new-us": "dev-new-us.jsonl.gz",
    "partial": "dev-partial.jsonl.gz",
    "reordered": "dev-reordered.jsonl.gz",
    "combined": "dev-combined.jsonl.gz",
    "zip-first": "dev-zip-first.jsonl.gz",
}
ROBUST_PANEL_COUNTRIES = {
    "clean": {"us", "gb", "au", "nz", "ca", "ie", "za"},
    "old-us": {"us"},
    "new-us": {"us"},
    "partial": {"us", "gb", "au", "nz", "ca", "ie", "za"},
    "reordered": {"us", "gb", "au", "nz", "ca", "ie", "za"},
    "combined": {"us", "gb", "au", "nz", "ca", "ie", "za"},
    "zip-first": {"us", "gb", "au", "nz", "ca", "ie", "za"},
}


def country_macro(result):
    countries = result["countries"]
    if not countries or any(not value["rows"] for value in countries.values()):
        raise ValueError("Every validation panel must contain nonempty country slices")
    return sum(value["exact"] / value["rows"] for value in countries.values()) / len(countries)


def robustness_selection(panels, baseline):
    """Return locked int5 score and clean eligibility for one epoch."""
    macros = {name: country_macro(result) for name, result in panels.items()}
    score = sum(macros[name] for name in ("partial", "reordered", "combined")) / 3
    reasons = []
    if macros["clean"] < country_macro(baseline["clean"]) - 0.005:
        reasons.append("clean-country-macro")
    for panel in ("clean", "old-us", "new-us"):
        expected = baseline[panel]["countries"]
        actual = panels[panel]["countries"]
        if set(actual) != set(expected):
            reasons.append(f"{panel}-countries")
            continue
        for country, reference in expected.items():
            if actual[country]["rows"] != reference["rows"]:
                reasons.append(f"{panel}-{country}-rows")
            allowed = max(math.ceil(0.01 * reference["rows"]), 1)
            if actual[country]["exact"] < reference["exact"] - allowed:
                reasons.append(f"{panel}-{country}-exact")
    return score, macros["clean"], not reasons, reasons


def train(args):
    if args.robustness:
        if args.init or args.init_encoder:
            raise ValueError("Robustness retraining must start from scratch")
        if args.limit or args.dev_limit:
            raise ValueError("Robustness retraining requires the full frozen corpus and panels")
        if args.max_hours <= 0:
            raise ValueError("--max-hours must be positive")
        args.seed = 2026
        args.batch_size = 128
        args.lr = 0.002
        args.country_balanced_loss = True
        args.case_augmentation = True
    if args.init_encoder and not args.init:
        raise ValueError("--init-encoder requires --init")
    if args.epochs < 1 or args.patience < 0:
        raise ValueError("Positive epochs and nonnegative patience required")
    country_weights = None
    if args.country_balanced_loss:
        if args.limit:
            raise ValueError("Country-balanced loss requires the full manifest training split")
        counts = json.loads((args.data / "manifest.json").read_text())["split_countries"]["train"]
        total = sum(counts.values())
        country_weights = {c: total / (len(counts) * n) for c, n in counts.items()}
    if args.threads:
        torch.set_num_threads(args.threads)
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    case_rng = random.Random(args.seed)
    structural_rng = random.Random(2026)
    device = torch.device(
        args.device
        if args.device != "auto"
        else ("mps" if torch.backends.mps.is_available() else "cpu")
    )
    if (args.run / "run.json").exists():
        raise ValueError("Use a new run directory; existing experiment must not be overwritten")
    with ExitStack() as stack:
        train_file = None
        if args.limit:
            train_data, train_rejected = load(
                args.data / "train.jsonl.gz",
                gap_features=args.gap_features,
                limit=args.limit,
                seed=args.seed,
            )
        else:
            args.run.parent.mkdir(parents=True, exist_ok=True)
            train_file = stack.enter_context(tempfile.TemporaryFile(dir=args.run.parent))
            train_data, train_rejected = spool(
                args.data / "train.jsonl.gz", train_file, gap_features=args.gap_features
            )
        dev_data, dev_rejected = load(
            args.data / "dev.jsonl.gz",
            gap_features=args.gap_features,
            limit=args.dev_limit,
            seed=71,
        )
        panel_data = {"clean": (dev_data, dev_rejected)}
        baseline = None
        baseline_path = args.data / "baseline-int5.json"
        conflict_path = args.data / "augmentation-conflicts.json"
        blocked = frozenset()
        if args.robustness:
            baseline = json.loads(baseline_path.read_text())
            if set(baseline) != set(ROBUST_PANELS):
                raise ValueError("baseline-int5.json must contain every locked validation panel")
            for name, countries in ROBUST_PANEL_COUNTRIES.items():
                if country_weights is not None and set(country_weights) == {"us"}:
                    countries = {"us"}
                if set(baseline[name]["countries"]) != countries:
                    raise ValueError(f"Baseline {name} panel has incomplete country coverage")
            for name, filename in ROBUST_PANELS.items():
                if name != "clean":
                    panel_data[name] = load(
                        args.data / filename, gap_features=args.gap_features, seed=71
                    )
            conflict_keys = json.loads(conflict_path.read_text())
            if not isinstance(conflict_keys, list) or not all(
                isinstance(key, str) for key in conflict_keys
            ):
                raise ValueError("augmentation-conflicts.json must be a JSON list of keys")
            blocked = frozenset(conflict_keys)
        if not train_data or not dev_data:
            raise ValueError("Training and development sets must contain supported examples")
        if country_weights and (train_rejected or len(train_data) != total):
            raise ValueError("Training counts differ from country-weight manifest")
        model = Tagger(architecture=ARCHITECTURE, gap_features=args.gap_features).to(device)
        parent = None
        if args.init:
            checkpoint = torch.load(args.init, map_location="cpu", weights_only=False)
            if args.init_encoder:
                expected = dict(model.config, architecture="ordered-byte-conv32-scan128-v2")
                if checkpoint["metadata"]["config"] != expected:
                    raise ValueError("Encoder transfer requires the previous H128 architecture")
                head = {
                    "output.weight",
                    "output.bias",
                    "transitions",
                    "start",
                    "end",
                    "allowed",
                    "start_allowed",
                }
                state = model.state_dict()
                state.update({k: v for k, v in checkpoint["model"].items() if k not in head})
                model.load_state_dict(state)
            else:
                if (
                    checkpoint["metadata"]["config"] != model.config
                    or checkpoint["metadata"]["labels"] != LABELS
                ):
                    raise ValueError(
                        "Initialization architecture/labels do not match requested model"
                    )
                model.load_state_dict(checkpoint["model"])
            parent = dict(
                path=str(args.init),
                sha256=file_sha256(args.init),
                initialization=(
                    "previous H128 encoder only; fresh seven-label output/CRF"
                    if args.init_encoder
                    else "weights only"
                )
                + "; fresh AdamW and explicitly requested learning rate",
            )
        optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
        scheduler = (
            torch.optim.lr_scheduler.ReduceLROnPlateau(
                optimizer,
                mode="max",
                factor=0.5,
                patience=0,
                threshold=0.0001,
                threshold_mode="abs",
                min_lr=0.00001,
            )
            if args.patience and not args.robustness
            else None
        )
        args.run.mkdir(parents=True, exist_ok=True)
        source_hashes = {file.name: file_sha256(file) for file in sorted(SOURCE.glob("*.py"))}
        data_names = (
            list(ROBUST_PANELS.values()) if args.robustness else ["train.jsonl.gz", "dev.jsonl.gz"]
        )
        if args.robustness:
            data_names.insert(0, "train.jsonl.gz")
        metadata = dict(
            seed=args.seed,
            config=model.config,
            labels=LABELS,
            device=str(device),
            parent=parent,
            torch=torch.__version__,
            python=platform.python_version(),
            platform=platform.platform(),
            parameters=sum(p.numel() for p in model.parameters()),
            train_rows=len(train_data),
            training_storage="temporary-jsonl-uint64-offsets"
            if train_file is not None
            else "in-memory-sample",
            dev_rows=len(dev_data),
            rejected=dict(train=train_rejected, dev=dev_rejected),
            data_manifest_sha256=file_sha256(args.data / "manifest.json"),
            data_files={name: file_sha256(args.data / name) for name in data_names},
            validation_panels=(
                {
                    name: dict(file=filename, sha256=file_sha256(args.data / filename))
                    for name, filename in ROBUST_PANELS.items()
                }
                if args.robustness
                else None
            ),
            baseline_int5_sha256=(file_sha256(baseline_path) if args.robustness else None),
            augmentation_conflicts=(
                dict(sha256=file_sha256(conflict_path), keys=len(blocked))
                if args.robustness
                else None
            ),
            code_sha256=source_hashes,
            arguments={k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
            target="field parsing pilot; no calibrated input-status or release accuracy claim",
            architecture=ARCHITECTURE,
            country_loss_weights=country_weights,
            selection_metric=(
                "int5 mean country macro: partial/reordered/combined, clean-gated"
                if args.robustness
                else args.selection_metric
            ),
            case_augmentation=(
                "Uniform per-presentation original/lower/upper/title token-byte features; "
                "independent seed-matched RNG; unchanged source spans; byte-limit fallback to original"
                if args.case_augmentation
                else "none"
            ),
            structural_augmentation=(
                "locked 50/25/15/10 original/partial/reordered/combined; RNG seed 2026"
                if args.robustness
                else "none"
            ),
        )
        (args.run / "run.json").write_text(json.dumps(metadata, indent=2))
        (args.run / "source").mkdir(exist_ok=True)
        for name in source_hashes:
            shutil.copy2(SOURCE / name, args.run / "source" / name)
        shutil.copy2(args.data / "manifest.json", args.run / "data-manifest.json")
        if args.robustness:
            shutil.copy2(baseline_path, args.run / "baseline-int5.json")
            shutil.copy2(conflict_path, args.run / "augmentation-conflicts.json")
        print(json.dumps(metadata), flush=True)
        started = time.monotonic()
        best = -1
        best_key = None
        best_epoch = None
        best_robustness = -1
        stale = 0
        lr_stale = 0
        epoch_durations = []
        stop_reason = "epoch-budget"
        for epoch in range(1, args.epochs + 1):
            epoch_started = time.monotonic()
            model.train()
            random.shuffle(train_data)
            total = 0
            case_counts = Counter()
            for step, start in enumerate(range(0, len(train_data), args.batch_size)):
                selected = train_data[start : start + args.batch_size]
                if train_file is not None:
                    selected = read_batch(train_file, selected, gap_features=args.gap_features)
                if args.robustness:
                    augmented = []
                    for item in selected:
                        changed, mode = structural_variant(
                            item, structural_rng, blocked=blocked, gap_features=args.gap_features
                        )
                        case_counts[f"structural:{mode}"] += 1
                        augmented.append(changed)
                    selected = augmented
                if args.case_augmentation:
                    augmented = []
                    for item in selected:
                        mode = case_rng.choice(("original", "lower", "upper", "title"))
                        changed = case_variant(item, mode)
                        case_counts[mode] += 1
                        case_counts["byte_limit_fallback"] += mode != "original" and changed is item
                        augmented.append(changed)
                    selected = augmented
                x, gold, lengths, ordered = batch(selected, device)
                weights = (
                    torch.tensor([country_weights[r[3]["country"]] for r in ordered], device=device)
                    if country_weights
                    else None
                )
                optimizer.zero_grad(set_to_none=True)
                loss = model.loss(model(x, lengths), gold, lengths, weights)
                if not torch.isfinite(loss):
                    raise ValueError("Non-finite loss")
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), 5)
                optimizer.step()
                total += loss.item()
                if step % 50 == 0:
                    print(
                        json.dumps(
                            dict(
                                epoch=epoch,
                                step=step,
                                loss=loss.item(),
                                elapsed_s=round(time.monotonic() - started, 1),
                            )
                        ),
                        flush=True,
                    )
            eligible = True
            if args.robustness:
                _, deployed, max_error = serialize(model, quantized=True, bits=5)
                deployed.to(device)
                int5 = {
                    name: evaluate(
                        deployed,
                        values,
                        device,
                        args.batch_size,
                        unsupported=rejected,
                    )
                    for name, (values, rejected) in panel_data.items()
                }
                result = dict(int5["clean"])
                metric, clean_macro, eligible, guard_failures = robustness_selection(int5, baseline)
                result["int5"] = int5
                result["int5_max_parameter_error"] = max_error
                result["robustness_score"] = metric
                result["int5_clean_country_macro_accuracy"] = clean_macro
                result["eligible"] = eligible
                result["clean_guard_failures"] = guard_failures
            else:
                result = evaluate(
                    model,
                    dev_data,
                    device,
                    args.batch_size,
                    unsupported=None if args.dev_limit else dev_rejected,
                )
                clean_macro = country_macro(result)
                result["country_macro_accuracy"] = clean_macro
                metric = result[args.selection_metric]
            result.update(
                epoch=epoch, train_loss=total / (step + 1), elapsed_s=time.monotonic() - started
            )
            result["country_macro_accuracy"] = clean_macro
            result["learning_rate"] = optimizer.param_groups[0]["lr"]
            if args.robustness:
                score_improved = metric >= best_robustness + 0.0001
                if score_improved:
                    best_robustness = metric
                    stale = 0
                    lr_stale = 0
                else:
                    stale += 1
                    lr_stale += 1
                selection_key = (metric, clean_macro, -epoch)
                improved = eligible and (best_key is None or selection_key > best_key)
                if improved:
                    best_key = selection_key
                    best = metric
            else:
                improved = metric > best
                stale = 0 if improved else stale + 1
            if scheduler:
                scheduler.step(metric)
            elif args.robustness and lr_stale >= 2:
                for group in optimizer.param_groups:
                    group["lr"] = max(group["lr"] * 0.5, 0.00001)
                lr_stale = 0
            if args.case_augmentation:
                result["case_augmentation_choices"] = dict(case_counts)
            (args.run / f"epoch-{epoch}.json").write_text(
                json.dumps(result, indent=2, ensure_ascii=False)
            )
            checkpoint = dict(
                model=model.cpu().state_dict(),
                optimizer=optimizer.state_dict(),
                metadata=metadata,
                epoch=epoch,
                metric=metric,
                torch_rng=torch.get_rng_state(),
                python_rng=random.getstate(),
                case_rng=case_rng.getstate(),
                structural_rng=structural_rng.getstate(),
            )
            torch.save(checkpoint, args.run / "last.pt")
            torch.save(checkpoint, args.run / f"epoch-{epoch}.pt")
            if improved:
                best = metric
                best_epoch = epoch
                torch.save(checkpoint, args.run / "best.pt")
            model.to(device)
            print(
                json.dumps(
                    {
                        k: v
                        for k, v in result.items()
                        if k not in ["countries", "fields", "failures"]
                    }
                ),
                flush=True,
            )
            epoch_durations.append(time.monotonic() - epoch_started)
            if args.robustness and epoch >= 12 and stale >= 6:
                stop_reason = "validation-plateau"
                break
            if args.robustness and (
                time.monotonic() - started + max(epoch_durations[-3:]) > args.max_hours * 3600
            ):
                stop_reason = "time-budget"
                break
            if not args.robustness and args.patience and stale >= args.patience:
                stop_reason = "validation-plateau"
                break
        completion = dict(
            status="completed",
            epochs=epoch,
            best_validation_metric=best,
            best_epoch=best_epoch,
            selection_metric=("int5_robustness" if args.robustness else args.selection_metric),
            stop_reason=stop_reason,
            elapsed_s=time.monotonic() - started,
        )
        (args.run / "completion.json").write_text(json.dumps(completion, indent=2))
        print(json.dumps(completion), flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=ROOT / "data")
    ap.add_argument("--run", type=Path, default=ROOT / "runs" / "pilot-2026")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--epochs", type=int)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--threads", type=int, default=0)
    ap.add_argument("--lr", type=float, default=0.002)
    ap.add_argument("--init", type=Path)
    ap.add_argument(
        "--init-encoder",
        action="store_true",
        help="Transfer old H128 backbone; initialize a fresh seven-label head",
    )
    ap.add_argument("--gap-features", action="store_true")
    ap.add_argument("--case-augmentation", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dev-limit", type=int, default=0)
    ap.add_argument("--country-balanced-loss", action="store_true")
    ap.add_argument(
        "--robustness",
        action="store_true",
        help="Use the locked from-scratch int5 robustness retraining recipe",
    )
    ap.add_argument("--max-hours", type=float, default=10)
    ap.add_argument(
        "--selection-metric",
        choices=["exact_accuracy", "country_macro_accuracy"],
        default="exact_accuracy",
    )
    ap.add_argument(
        "--patience",
        type=int,
        default=0,
        help="Stop after N plateau epochs; halve LR on each plateau",
    )
    args = ap.parse_args(argv)
    if args.epochs is None:
        args.epochs = 2**31 - 1 if args.robustness else 3
    train(args)
