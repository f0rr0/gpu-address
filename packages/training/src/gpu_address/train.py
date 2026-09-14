"""Explicit PyTorch training loop and checkpoint provenance."""

import argparse
import hashlib
import json
import platform
import random
import shutil
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn

from .data import batch, load
from .evaluate import evaluate
from .model import Tagger
from .paths import ROOT, SOURCE
from .schema import LABELS


def train(args):
    torch.set_num_threads(args.threads)
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = torch.device(
        args.device
        if args.device != "auto"
        else ("mps" if torch.backends.mps.is_available() else "cpu")
    )
    train_data, train_rejected = load(
        args.data / "train.jsonl.gz",
        gap_features=args.gap_features,
        limit=args.limit,
        seed=args.seed,
    )
    dev_data, dev_rejected = load(
        args.data / "dev.jsonl.gz", gap_features=args.gap_features, limit=args.dev_limit, seed=71
    )
    if not train_data or not dev_data:
        raise ValueError("Training and development sets must contain supported examples")
    model = Tagger(args.hidden, gap_features=args.gap_features).to(device)
    parent = None
    if args.init:
        checkpoint = torch.load(args.init, map_location="cpu", weights_only=False)
        if any(
            checkpoint["metadata"]["config"][key] != model.config[key]
            for key in ["hidden", "layers"]
        ):
            raise ValueError("Initialization architecture does not match requested model")
        model.load_state_dict(checkpoint["model"])
        parent = dict(
            path=str(args.init),
            sha256=hashlib.sha256(args.init.read_bytes()).hexdigest(),
            initialization="weights only; fresh AdamW and explicitly requested learning rate",
        )
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    if (args.run / "run.json").exists():
        raise ValueError("Use a new run directory; existing experiment must not be overwritten")
    args.run.mkdir(parents=True, exist_ok=True)
    manifest_bytes = (args.data / "manifest.json").read_bytes()
    source_hashes = {
        file.name: hashlib.sha256(file.read_bytes()).hexdigest()
        for file in sorted(SOURCE.glob("*.py"))
    }
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
        dev_rows=len(dev_data),
        rejected=dict(train=train_rejected, dev=dev_rejected),
        data_manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        data_files={
            name: hashlib.sha256((args.data / name).read_bytes()).hexdigest()
            for name in ["train.jsonl.gz", "dev.jsonl.gz"]
        },
        code_sha256=source_hashes,
        arguments={k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
        target="field parsing pilot; no calibrated input-status or release accuracy claim",
    )
    (args.run / "run.json").write_text(json.dumps(metadata, indent=2))
    (args.run / "source").mkdir(exist_ok=True)
    for name in source_hashes:
        shutil.copy2(SOURCE / name, args.run / "source" / name)
    shutil.copy2(args.data / "manifest.json", args.run / "data-manifest.json")
    print(json.dumps(metadata), flush=True)
    started = time.monotonic()
    best = -1
    for epoch in range(1, args.epochs + 1):
        model.train()
        random.shuffle(train_data)
        total = 0
        for step, start in enumerate(range(0, len(train_data), args.batch_size)):
            x, gold, lengths, _ = batch(train_data[start : start + args.batch_size], device)
            optimizer.zero_grad(set_to_none=True)
            loss = model.loss(model(x, lengths), gold, lengths)
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
        result = evaluate(model, dev_data, device, args.batch_size)
        result.update(
            epoch=epoch, train_loss=total / (step + 1), elapsed_s=time.monotonic() - started
        )
        (args.run / f"epoch-{epoch}.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False)
        )
        checkpoint = dict(
            model=model.cpu().state_dict(),
            optimizer=optimizer.state_dict(),
            metadata=metadata,
            epoch=epoch,
            metric=result["exact_accuracy"],
            torch_rng=torch.get_rng_state(),
            python_rng=random.getstate(),
        )
        torch.save(checkpoint, args.run / "last.pt")
        if result["exact_accuracy"] > best:
            best = result["exact_accuracy"]
            torch.save(checkpoint, args.run / "best.pt")
        model.to(device)
        print(
            json.dumps(
                {k: v for k, v in result.items() if k not in ["countries", "fields", "failures"]}
            ),
            flush=True,
        )


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=ROOT / "data")
    ap.add_argument("--run", type=Path, default=ROOT / "runs" / "pilot-2026")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--hidden", type=int, default=144)
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--lr", type=float, default=0.002)
    ap.add_argument("--init", type=Path)
    ap.add_argument("--gap-features", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dev-limit", type=int, default=0)
    train(ap.parse_args(argv))
