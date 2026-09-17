"""Independently rescore cached predictions; no training/evaluation imports.

Run from any directory with Python's standard library. This checks published
counts and exposes completeness effects; it is not a new unseen benchmark.
"""

import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data/website-benchmark"
MODELS = ("gpu", "libpostal", "senzing", "deepparse")
SHARED = {"street_address", "city", "state", "postcode"}
GROUPS = {
    "street_address": "house house_number road unit level staircase entrance po_box near",
    "locality": "suburb city_district island",
    "district": "state_district",
    "state": "country_region",
}
LABELS = {source: target for target, sources in GROUPS.items() for source in sources.split()}


def fields(parts):
    result = defaultdict(Counter)
    for part in parts:
        label = part["label"]
        if label in {"category", "world_region"}:
            continue
        text = unicodedata.normalize("NFKC", part["raw"]).casefold()
        result[LABELS.get(label, label)].update(re.findall(r"\w+|[^\w\s,]", text))
    return {label: tokens for label, tokens in result.items() if tokens}


def main():
    rows = json.loads((DATA / "inputs.json").read_text())
    published = json.loads((ROOT / "apps/website/public/benchmarks.json").read_text())
    assert (
        hashlib.sha256((DATA / "source.csv").read_bytes()).hexdigest()
        == published["source"]["sha256"]
    )
    gold = {r["id"]: fields(r["components"]) for r in rows}
    correct = {}
    for model in MODELS:
        raw = (DATA / f"{model}.json").read_bytes()
        assert hashlib.sha256(raw).hexdigest() == published["prediction_sha256"][model]
        predictions = json.loads(raw)
        assert set(predictions) == set(gold)
        correct[model] = {key: fields(parts) == gold[key] for key, parts in predictions.items()}
    output = []
    for country in [None, *[c["country"] for c in published["countries"]]]:
        candidates = [r for r in rows if country is None or r["country"] == country]
        for scope in ("all", "shared", "complete", "partial_shared"):
            selected = [
                r
                for r in candidates
                if (
                    scope == "all"
                    or scope == "shared"
                    and set(gold[r["id"]]) <= SHARED
                    or scope == "complete"
                    and set(gold[r["id"]]) == SHARED
                    or scope == "partial_shared"
                    and set(gold[r["id"]]) < SHARED
                )
            ]
            counts = {m: sum(correct[m][r["id"]] for r in selected) for m in MODELS}
            if country:
                expected = next(c for c in published["countries"] if c["country"] == country)
                if scope != "all":
                    expected = expected["partial" if scope == "partial_shared" else scope]
                assert expected["rows"] == len(selected)
                assert all(expected[m] == counts[m] for m in MODELS)
            output.append(dict(country=country or "all", scope=scope, rows=len(selected), **counts))
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
