"""US-only supplement to frozen v4 data. No fitting or input selection.

uv run --with usaddress==0.5.16 --with brotli==1.2.0 python packages/training/scripts/usaddress_benchmark.py
"""

import hashlib
import json
from collections import Counter, defaultdict
from importlib.metadata import version
from pathlib import Path

import brotli
import usaddress  # ty: ignore[unresolved-import]  # Optional comparator: uv run --with usaddress
from audit_website_benchmark import fields
from external_benchmark import interval

PUBLIC = Path(__file__).resolve().parents[3] / "apps/website/public/evaluation-v4"
LABELS = {label: "street_address" for label in usaddress.LABELS}
LABELS.update(PlaceName="city", StateName="state", ZipCode="postcode", NotAddress="unrecognized")
LABELS.update(CountryName="country", ZipPlus4="postcode", StreetNamePostModifier="street_address")


def projected(parts):
    merged = defaultdict(Counter)
    for label, tokens in fields(parts).items():
        merged[{"locality": "street_address", "district": "state"}.get(label, label)].update(tokens)
    return dict(merged)


def score(rows, predictions):
    correct = matches = actual_count = gold_count = 0
    breakdown = defaultdict(Counter)
    for row in rows:
        actual, gold = projected(predictions[row["id"]]), projected(row["components"])
        correct += actual == gold
        for label in actual.keys() | gold.keys():
            counts = breakdown[label]
            counts["rows"] += label in gold
            counts["predicted"] += label in actual
            counts["correct"] += label in actual and label in gold and actual[label] == gold[label]
        matches += sum(actual.get(k) == v for k, v in gold.items())
        actual_count += len(actual)
        gold_count += len(gold)
    return dict(
        correct=correct,
        percent=100 * correct / len(rows),
        interval=interval(correct, len(rows)),
        field_f1=200 * matches / (actual_count + gold_count),
        fields={
            label: dict(counts, f1=200 * counts["correct"] / (counts["rows"] + counts["predicted"]))
            for label, counts in breakdown.items()
        },
    )


def main():
    assert version("usaddress") == "0.5.16"
    raw = (PUBLIC / "inputs.json").read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    report = json.loads((PUBLIC / "results.json").read_text())
    assert digest == report["manifest"]["inputs_sha256"]
    rows = [r for r in json.loads(raw) if r["country"] == "us" and r["cohort"] == "complete"]
    assert len(rows) == 842
    # Check the supplement scorer against the previously published US result.
    gpu = json.loads((PUBLIC / "gpu.json").read_text())
    expected = next(
        g for g in report["groups"] if g["country"] == "us" and g["cohort"] == "complete"
    )["models"]["gpu"]
    measured = score(rows, gpu)
    assert measured["correct"] == expected["correct"]
    assert abs(measured["field_f1"] - expected["field_f1"]) < 1e-10
    predictions = {
        row["id"]: [
            dict(label=LABELS[label], raw=token, source_label=label)
            for token, label in usaddress.parse(row["text"])
        ]
        for row in rows
    }
    # Preserve every parser token; tokenizer omissions remain scoring errors.
    for row in rows:
        token_fields = fields([dict(label="all", raw=p["raw"]) for p in predictions[row["id"]]])
        assert token_fields == fields(
            [dict(label="all", raw=t) for t in usaddress.tokenize(row["text"])]
        )
    prediction_bytes = (json.dumps(predictions, indent=2) + "\n").encode()
    (PUBLIC / "usaddress.json").write_bytes(prediction_bytes)
    model = Path(usaddress.MODEL_PATH).read_bytes()
    result = dict(
        model="usaddress 0.5.16",
        country="us",
        cohort="complete",
        rows=len(rows),
        inputs_sha256=digest,
        prediction_sha256=hashlib.sha256(prediction_bytes).hexdigest(),
        versions={
            p: version(p) for p in ("usaddress", "python-crfsuite", "probableparsing", "brotli")
        },
        label_mapping=LABELS,
        method="Default usaddress.parse; no training. US complete cohort only. Same exact-field token-multiset scorer. Non-address tokens remain errors. Other parser results and frozen inputs unchanged. Competitor training overlap unknown.",
        score=score(rows, predictions),
        size=dict(
            bytes=len(brotli.compress(model, quality=5)),
            uncompressed_bytes=len(model),
            model_sha256=hashlib.sha256(model).hexdigest(),
            file="usaddr.crfsuite",
            compression="Brotli quality 5; model only; Python, CRFsuite and feature-extraction code excluded.",
        ),
    )
    (PUBLIC / "usaddress-results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(dict(score=result["score"], size=result["size"]), indent=2))


if __name__ == "__main__":
    main()
