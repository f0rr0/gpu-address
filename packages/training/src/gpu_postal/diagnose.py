"""Fixed-set error analysis; the public suite is development evidence, not gold."""

import argparse
import gzip
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

import torch

from .data import batch, load
from .evaluate import evaluate, field_exact, field_tokens
from .model import Tagger
from .paths import ROOT
from .tokenizer import components


def saved_exact(saved, truth):
    """Recompute compatible saved predictions; old field-map-only files are incomparable."""
    parts = saved.get("predicted_components", saved.get("teacher_components"))
    if not isinstance(parts, list):
        return None
    try:
        return field_exact(parts, truth)
    except KeyError:
        return None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--data", type=Path, default=ROOT / "data/layout-independent")
    ap.add_argument(
        "--baseline", type=Path, default=ROOT / "data/expanded/baseline-predictions.jsonl.gz"
    )
    ap.add_argument("--compare", type=Path)
    ap.add_argument("--source-dev", type=Path, help="Evaluate only this supplementary labeled set")
    args = ap.parse_args(argv)
    torch.set_num_threads(3)
    saved = torch.load(args.run / "best.pt", map_location="cpu", weights_only=False)
    model = Tagger(**saved["metadata"]["config"])
    model.load_state_dict(saved["model"])
    model.eval()
    if args.source_dev:
        rows, rejected = load(args.source_dev, gap_features=model.config["gap_features"])
        result = evaluate(model, rows, "cpu", unsupported=rejected)
        result.update(
            rejected=rejected,
            data_sha256=hashlib.sha256(args.source_dev.read_bytes()).hexdigest(),
            scope="supplementary source-derived labels, not independent human gold",
        )
        (args.run / "source-dev.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(
            json.dumps(
                {k: v for k, v in result.items() if k not in ["countries", "fields", "failures"]},
                indent=2,
            )
        )
        return
    with gzip.open(args.baseline, "rt") as source:
        baseline = {row["id"]: row for row in map(json.loads, source)}
    earlier = {}
    if args.compare:
        with gzip.open(args.compare / "diagnostic-predictions.jsonl.gz", "rt") as source:
            earlier = {row["id"]: row for row in map(json.loads, source)}
    public, rejected = load(
        args.data / "public-benchmark.jsonl.gz", False, model.config["gap_features"]
    )
    counts, missing, extra, changed, confusions = (
        Counter(),
        Counter(),
        Counter(),
        Counter(),
        Counter(),
    )
    countries, field_stats = defaultdict(Counter), defaultdict(Counter)
    predictions = []
    with torch.no_grad():
        for start in range(0, len(public), 64):
            x, _, lengths, rows = batch(public[start : start + 64], "cpu")
            emissions = model(x, lengths)
            paths = model.decode(emissions, lengths)
            argmax = emissions.argmax(-1).tolist()
            for i, (path, (_, _, offsets, row)) in enumerate(zip(paths, rows)):
                predicted_components = components(path, offsets, row["text"])
                predicted = field_tokens(predicted_components)
                truth = field_tokens(row["components"])
                exact = predicted == truth
                oracle_exact = saved_exact(baseline[row["id"]], row["components"])
                counts["rows"] += 1
                counts["exact"] += exact
                if oracle_exact is None:
                    counts["teacher_comparison_incompatible"] += 1
                else:
                    counts[f"student_{exact}_teacher_{oracle_exact}"] += 1
                greedy = field_tokens(components(argmax[i][: len(path)], offsets, row["text"]))
                counts["argmax_exact"] += greedy == truth
                counts["argmax_right_crf_wrong"] += greedy == truth and not exact
                counts["crf_right_argmax_wrong"] += exact and greedy != truth
                countries[row["country"]]["rows"] += 1
                countries[row["country"]]["exact"] += exact
                if oracle_exact is not None:
                    countries[row["country"]]["teacher_rows"] += 1
                    countries[row["country"]]["teacher_exact"] += oracle_exact
                for field in truth.keys() | predicted.keys():
                    field_stats[field]["present_gold"] += field in truth
                    field_stats[field]["correct"] += (
                        field in truth and predicted.get(field) == truth[field]
                    )
                    if field not in predicted:
                        missing[field] += 1
                    elif field not in truth:
                        extra[field] += 1
                    elif predicted[field] != truth[field]:
                        changed[field] += 1
                for field, value in truth.items():
                    if predicted.get(field) != value:
                        for other, got in predicted.items():
                            if other != field and got == value:
                                confusions[f"{field}->{other}"] += 1
                if earlier:
                    before = saved_exact(earlier[row["id"]], row["components"])
                    if before is None:
                        counts["earlier_comparison_incompatible"] += 1
                    else:
                        counts["newly_wrong"] += before and not exact
                        counts["newly_correct"] += not before and exact
                predictions.append(
                    dict(
                        id=row["id"],
                        country=row["country"],
                        text=row["text"],
                        gold=truth,
                        predicted=predicted,
                        predicted_components=predicted_components,
                        exact=exact,
                        teacher_exact=oracle_exact,
                    )
                )
    training_path = Path(saved["metadata"]["arguments"]["data"]) / "train.jsonl.gz"
    if (
        hashlib.sha256(training_path.read_bytes()).hexdigest()
        != saved["metadata"]["data_files"]["train.jsonl.gz"]
    ):
        raise ValueError("Training data no longer matches checkpoint provenance")
    # Reconstruct the training sample before selecting the diagnostic subset.
    train, _ = load(
        training_path,
        gap_features=model.config["gap_features"],
        limit=saved["metadata"]["arguments"]["limit"],
        seed=saved["metadata"]["seed"],
    )
    train = random.Random(91).sample(train, min(3000, len(train)))
    train_result = evaluate(model, train, "cpu")
    report = dict(
        counts=counts,
        public_accuracy=counts["exact"] / (counts["rows"] + rejected),
        rejected=rejected,
        missing_fields=missing,
        extra_fields=extra,
        wrong_field_content=changed,
        exact_value_label_confusions=confusions,
        countries=countries,
        field_stats=field_stats,
        training_sample=dict(rows=len(train), exact_accuracy=train_result["exact_accuracy"]),
        scope="fixed public development benchmark; no independent final accuracy claim",
    )
    (args.run / "diagnosis.json").write_text(json.dumps(report, indent=2))
    with gzip.open(args.run / "diagnostic-predictions.jsonl.gz", "wt") as destination:
        for row in predictions:
            destination.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {k: v for k, v in report.items() if k not in ["countries", "field_stats"]}, indent=2
        )
    )


if __name__ == "__main__":
    main()
