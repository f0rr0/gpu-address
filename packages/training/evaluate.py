"""Exact-span and per-field evaluation."""

import re
import unicodedata
from collections import Counter, defaultdict

import torch

from .data import batch
from .schema import FIELD_MAP
from .tokenizer import components


def field_tokens(parts):
    """Seven-field token multisets; ignore order, commas, case and whitespace."""
    result = defaultdict(Counter)
    for part in parts:
        label = FIELD_MAP[part["label"]]
        if label is not None:
            value = unicodedata.normalize("NFKC", part["raw"]).casefold()
            result[label].update(re.findall(r"\w+|[^\w\s,]", value))
    return {label: tokens for label, tokens in result.items() if tokens}


def field_exact(predicted, expected):
    return field_tokens(predicted) == field_tokens(expected)


@torch.no_grad()
def evaluate(model, data, device, batch_size=64, *, unsupported=0):
    """Evaluate encodable rows; unsupported is the matching encode-rejected count.

    Pass ``None`` when that count covers a different population, such as a
    bounded sample drawn only from supported rows.
    """
    if unsupported is not None and (type(unsupported) is not int or unsupported < 0):
        raise ValueError("unsupported must be a nonnegative integer or None")
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
    evaluated = counts["rows"]
    total = None if unsupported is None else evaluated + unsupported
    supported_accuracy = counts["exact"] / max(evaluated, 1)
    return dict(
        **counts,
        evaluated=evaluated,
        unsupported=unsupported,
        total=total,
        ordered_span_accuracy_supported=supported_accuracy,
        ordered_span_accuracy_all_inputs=(
            None if total is None else counts["exact"] / max(total, 1)
        ),
        exact_accuracy=supported_accuracy,
        token_accuracy=counts["correct_tokens"] / max(counts["tokens"], 1),
        countries={k: dict(v) for k, v in countries.items()},
        fields={k: dict(v) for k, v in fields.items()},
        failures=failures,
    )
