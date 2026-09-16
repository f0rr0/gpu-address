"""Evaluate seven-label checkpoints on the frozen diagnostics, never select by test."""

import argparse
import inspect
import json
from collections import Counter, defaultdict
from pathlib import Path

import torch
from gpu_postal.consolidate import rows
from gpu_postal.data import batch
from gpu_postal.evaluate import field_tokens as fields
from gpu_postal.expand import file_sha256
from gpu_postal.model import Tagger
from gpu_postal.schema import LABELS, seven_fields
from gpu_postal.tokenizer import components, encode


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("checkpoint", type=Path)
    ap.add_argument("--holdout", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    torch.set_num_threads(2)
    saved = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    if saved["metadata"]["labels"] != LABELS:
        raise ValueError("Checkpoint does not use seven labels")
    model = Tagger(**saved["metadata"]["config"])
    model.load_state_dict(saved["model"])
    model.eval()
    paths = [Path("data/competitor-comparison-20260916/inputs.jsonl")]
    records = list(rows(paths[0]))
    if args.holdout:
        paths.append(args.holdout)
        extra = list(rows(args.holdout))
        assert all(r["annotation_status"] == "accepted" for r in extra)
        records.extend(dict(r, evaluation_set="india-fresh", country="in") for r in extra)
    assert len({r["id"] for r in records}) == len(records)
    outcomes, groups = [], defaultdict(Counter)
    with torch.inference_mode():
        for i in range(0, len(records), 32):
            items = []
            predicted = {}
            for r in records[i : i + 32]:
                item = encode(r, labeled=False)
                if item is not None:
                    items.append(item)
            if items:
                x, _, lengths, ordered = batch(items, "cpu")
                for tags, (_, _, offsets, r) in zip(
                    model.decode(model(x, lengths), lengths), ordered
                ):
                    predicted[r["id"]] = components(tags, offsets, r["text"])
            for r in records[i : i + 32]:
                p = predicted.get(r["id"])
                truth = fields(r["components"])
                got = fields(p) if p is not None else None
                exact = got == truth
                span_eligible = all("start" in c for c in r["components"])
                span_exact = span_eligible and p == seven_fields(r)["components"]
                for group in (
                    r["evaluation_set"],
                    r["evaluation_set"] + ":" + r["country"].lower(),
                ):
                    counts = groups[group]
                    counts.update(
                        rows=1,
                        exact=int(exact),
                        unsupported=int(p is None),
                        span_eligible=int(span_eligible),
                        span_exact=int(span_exact),
                    )
                    for label in truth.keys() | (got or {}).keys():
                        counts["mismatch:" + label] += truth.get(label) != (got or {}).get(label)
                outcomes.append(
                    dict(
                        id=r["id"],
                        evaluation_set=r["evaluation_set"],
                        country=r["country"],
                        text=r["text"],
                        predicted=p,
                        exact=exact,
                        span_exact=span_exact,
                    )
                )
    args.output.mkdir(parents=True, exist_ok=False)
    with (args.output / "predictions.jsonl").open("x") as f:
        for r in outcomes:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    report = dict(
        checkpoint=str(args.checkpoint),
        checkpoint_sha256=file_sha256(args.checkpoint),
        epoch=saved["epoch"],
        inputs={str(p): file_sha256(p) for p in paths},
        metric="Exact seven-field token multisets; commas/case/whitespace/order ignored; separate exact ordered spans where gold offsets exist",
        groups=dict(groups),
        code_sha256=file_sha256(Path(__file__)),
        scoring_sha256=file_sha256(Path(inspect.getfile(fields))),
    )
    (args.output / "scores.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report["groups"], indent=2))


if __name__ == "__main__":
    main()
