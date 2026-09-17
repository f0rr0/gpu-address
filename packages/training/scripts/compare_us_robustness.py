"""Same-input coarse-field comparison, separate from exact-span model selection."""

import argparse
import json
from pathlib import Path
from typing import Any

import torch
import usaddress  # ty: ignore[unresolved-import]  # Optional comparator: uv run --with usaddress
from training.consolidate import rows
from training.data import batch
from training.expand import file_sha256
from training.export import serialize
from training.model import Tagger
from training.tokenizer import components, encode
from training.train import ROBUST_PANELS
from usaddress_benchmark import LABELS, score


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--split", choices=("dev", "test"), required=True)
    args = ap.parse_args()
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    model = Tagger(**checkpoint["metadata"]["config"])
    model.load_state_dict(checkpoint["model"])
    _, model, _ = serialize(model, quantized=True, bits=5)
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    model.to(device).eval()
    report: dict[str, Any] = dict(
        checkpoint_sha256=file_sha256(args.checkpoint),
        method="Same-input coarse-field token multiset; not exact spans. Competitor exposure unknown. Diagnostic only.",
        panels={},
    )
    files = {
        name: filename.replace("dev", args.split, 1) for name, filename in ROBUST_PANELS.items()
    }
    files["natural-diagnostic"] = "natural-diagnostic.jsonl.gz"
    for name, filename in files.items():
        path = args.data / filename
        values = list(rows(path))
        encoded = [encode(r, gap_features=model.config["gap_features"]) for r in values]
        assert all(item is not None for item in encoded)
        ours = {}
        with torch.inference_mode():
            for start in range(0, len(encoded), 128):
                x, _, lengths, ordered = batch(encoded[start : start + 128], device)
                predicted = model.decode(model(x, lengths), lengths)
                for tags, item in zip(predicted, ordered):
                    ours[item[3]["id"]] = components(tags, item[2], item[3]["text"])
        theirs = {
            r["id"]: [
                dict(label=LABELS[label], raw=token) for token, label in usaddress.parse(r["text"])
            ]
            for r in values
        }
        report["panels"][name] = dict(
            rows=len(values),
            sha256=file_sha256(path),
            gpu_postal=score(values, ours),
            usaddress=score(values, theirs),
        )
        print(
            json.dumps(
                dict(
                    panel=name,
                    gpu_postal=report["panels"][name]["gpu_postal"]["percent"],
                    usaddress=report["panels"][name]["usaddress"]["percent"],
                )
            ),
            flush=True,
        )
    args.output.write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
