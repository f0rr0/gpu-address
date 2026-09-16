"""Explicit PyTorch training loop and checkpoint provenance."""

import argparse
import json
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

from .data import batch, case_variant, load, read_batch, spool
from .evaluate import evaluate
from .expand import file_sha256
from .model import ARCHITECTURE, Tagger
from .paths import ROOT, SOURCE
from .schema import LABELS


def train(args):
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
            if args.patience
            else None
        )
        args.run.mkdir(parents=True, exist_ok=True)
        source_hashes = {file.name: file_sha256(file) for file in sorted(SOURCE.glob("*.py"))}
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
            data_files={
                name: file_sha256(args.data / name) for name in ["train.jsonl.gz", "dev.jsonl.gz"]
            },
            code_sha256=source_hashes,
            arguments={k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
            target="field parsing pilot; no calibrated input-status or release accuracy claim",
            architecture=ARCHITECTURE,
            country_loss_weights=country_weights,
            selection_metric=args.selection_metric,
            case_augmentation=(
                "Uniform per-presentation original/lower/upper/title token-byte features; "
                "independent seed-matched RNG; unchanged source spans; byte-limit fallback to original"
                if args.case_augmentation
                else "none"
            ),
        )
        (args.run / "run.json").write_text(json.dumps(metadata, indent=2))
        (args.run / "source").mkdir(exist_ok=True)
        for name in source_hashes:
            shutil.copy2(SOURCE / name, args.run / "source" / name)
        shutil.copy2(args.data / "manifest.json", args.run / "data-manifest.json")
        print(json.dumps(metadata), flush=True)
        started = time.monotonic()
        best = -1
        stale = 0
        for epoch in range(1, args.epochs + 1):
            model.train()
            random.shuffle(train_data)
            total = 0
            case_counts = Counter()
            for step, start in enumerate(range(0, len(train_data), args.batch_size)):
                selected = train_data[start : start + args.batch_size]
                if train_file is not None:
                    selected = read_batch(train_file, selected, gap_features=args.gap_features)
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
            result = evaluate(
                model,
                dev_data,
                device,
                args.batch_size,
                unsupported=None if args.dev_limit else dev_rejected,
            )
            result.update(
                epoch=epoch, train_loss=total / (step + 1), elapsed_s=time.monotonic() - started
            )
            result["country_macro_accuracy"] = sum(
                c["exact"] / c["rows"] for c in result["countries"].values()
            ) / len(result["countries"])
            metric = result[args.selection_metric]
            result["learning_rate"] = optimizer.param_groups[0]["lr"]
            improved = metric > best
            stale = 0 if improved else stale + 1
            if scheduler:
                scheduler.step(metric)
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
            )
            torch.save(checkpoint, args.run / "last.pt")
            torch.save(checkpoint, args.run / f"epoch-{epoch}.pt")
            if improved:
                best = metric
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
            if args.patience and stale >= args.patience:
                break
        completion = dict(
            status="completed",
            epochs=epoch,
            best_validation_metric=best,
            selection_metric=args.selection_metric,
            stop_reason="validation-plateau"
            if args.patience and stale >= args.patience
            else "epoch-budget",
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
    ap.add_argument("--epochs", type=int, default=3)
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
    train(ap.parse_args(argv))
