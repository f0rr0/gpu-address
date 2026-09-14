"""Exact-span and per-field evaluation."""

from collections import Counter, defaultdict

import torch

from .data import batch
from .tokenizer import components


@torch.no_grad()
def evaluate(model, data, device, batch_size=64):
    model.eval()
    counts = Counter()
    countries = defaultdict(Counter)
    fields = defaultdict(Counter)
    failures = []
    for start in range(0, len(data), batch_size):
        x, y, lengths, rows = batch(data[start : start + batch_size], device)
        paths = model.decode(model(x, lengths), lengths)
        for path, (_, gold, offsets, row) in zip(paths, rows):
            predicted = components(path, offsets, row["text"])
            expected = row["components"]
            exact = predicted == expected
            counts["rows"] += 1
            counts["exact"] += exact
            counts["tokens"] += len(gold)
            counts["correct_tokens"] += sum(a == b for a, b in zip(path, gold))
            countries[row["country"]]["rows"] += 1
            countries[row["country"]]["exact"] += exact
            actual = {(s["label"], s["start"], s["end"]) for s in predicted}
            truth = {(s["label"], s["start"], s["end"]) for s in expected}
            for label, _, _ in actual & truth:
                fields[label]["tp"] += 1
            for label, _, _ in actual - truth:
                fields[label]["fp"] += 1
            for label, _, _ in truth - actual:
                fields[label]["fn"] += 1
            if not exact and len(failures) < 50:
                failures.append(
                    dict(id=row["id"], text=row["text"], gold=expected, predicted=predicted)
                )
    return dict(
        **counts,
        exact_accuracy=counts["exact"] / max(counts["rows"], 1),
        token_accuracy=counts["correct_tokens"] / max(counts["tokens"], 1),
        countries={k: dict(v) for k, v in countries.items()},
        fields={k: dict(v) for k, v in fields.items()},
        failures=failures,
    )
