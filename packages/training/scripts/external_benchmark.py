"""Frozen external-source US/UK diagnostic. No training or parser-generated gold.

prepare/report: uv run python packages/training/scripts/external_benchmark.py MODE
gpu/libpostal/senzing: same command; deep: comparator venv with PYTHONPATH=packages.
Source downloads and provenance are recorded in the manifest; raw snapshots live
under data/independent-us-uk-20260917. Public inputs contain addresses only.
"""

import argparse
import csv
import hashlib
import json
import math
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import website_benchmark as harness

ROOT = harness.ROOT
DATA = ROOT / "data/independent-us-uk-20260917"
PUBLIC = ROOT / "apps/website/public/evaluation"
MODELS = ("gpu", "libpostal", "senzing", "deepparse")
SEED = "external-us-uk-v1-20260917"
COHORTS = ("complete", "no-postcode", "no-city", "no-street", "lowercase", "no-commas", "multiline")


def key(value):
    return re.sub(r"[^\w]", "", unicodedata.normalize("NFKC", value).casefold())


def entity_keys(row):
    from training.evaluate import FIELD_MAP

    values = defaultdict(list)
    for part in row["components"]:
        values[FIELD_MAP[part["label"]]].append(part["raw"])
    street = key(" ".join(values["street_address"]))
    return {
        (row["country"], street, field, key(" ".join(values[field])))
        for field in ("city", "postcode")
        if street and values[field]
    }


def render(identifier, country, stratum, values, source, separator=", "):
    text, parts = "", []
    for label, value in values:
        value = " ".join(str(value).split())
        if not value:
            continue
        if text:
            text += separator
        start = len(text)
        text += value
        parts.append(dict(label=label, raw=value, start=start, end=len(text)))
    return dict(
        id=identifier, country=country, stratum=stratum, text=text, components=parts, source=source
    )


def prepare():
    if (DATA / "manifest.json").exists():
        raise ValueError("Frozen benchmark exists; do not silently replace it")
    blocked = set()
    with sqlite3.connect(
        f"file:{ROOT}/data/english-seven-20260916/identities.sqlite?mode=ro", uri=True
    ) as db:
        for (payload,) in db.execute(
            "SELECT payload FROM rows WHERE split='train' AND conflict=0 AND country IN ('us','gb')"
        ):
            blocked.update(entity_keys(json.loads(payload)))
    for path in (
        ROOT / "data/website-benchmark/inputs.json",
        ROOT / "data/geosearch-sample-20260916/inputs.json",
    ):
        for row in json.loads(path.read_text()):
            blocked.update(entity_keys(dict(row, country=row.get("country", "us"))))
    pool, exclusions, used = defaultdict(list), Counter(), set()

    def admit(row):
        needed = {"street_address", "city", "postcode"} | (
            {"state"} if row["country"] == "us" else set()
        )
        if {p["label"] for p in row["components"]} != needed:
            exclusions["missing_required_field"] += 1
            return
        if "\ufffd" in row["text"]:
            raise ValueError("Source decoding lost characters")
        keys = entity_keys(row)
        if keys & blocked:
            exclusions["training_or_previous_evaluation_entity"] += 1
        elif keys & used:
            exclusions["duplicate_entity"] += 1
        else:
            used.update(keys)
            pool[row["stratum"]].append(row)

    states = set(
        "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split()
    )
    for path in sorted(DATA.glob("fdic-*.json")):
        for item in json.loads(path.read_text())["data"]:
            r = item["data"]
            if r["STALP"] not in states:
                exclusions["US_territory_or_foreign"] += 1
                continue
            admit(
                render(
                    f"fdic:{r['UNINUM']}",
                    "us",
                    r["STALP"],
                    [
                        (
                            "street_address",
                            " ".join([r.get("ADDRESS", ""), r.get("ADDRESS2", "")]).strip(),
                        ),
                        ("city", r["CITY"]),
                        ("state", r["STALP"]),
                        ("postcode", r["ZIP"]),
                    ],
                    path.name,
                )
            )
    # GIAS is Windows-1252, not UTF-8. Only explicitly typed core addresses are
    # eligible: don't guess whether extra address lines are streets or localities.
    english_regions = {
        "North East",
        "North West",
        "Yorkshire and the Humber",
        "East Midlands",
        "West Midlands",
        "East of England",
        "London",
        "South East",
        "South West",
    }
    with (DATA / "england.csv").open(encoding="cp1252", newline="") as stream:
        for r in csv.DictReader(stream):
            if r["EstablishmentStatus (name)"] != "Open" or r["GOR (name)"] not in english_regions:
                exclusions["England_closed_or_no_region"] += 1
                continue
            if r["Locality"].strip() or r["Address3"].strip():
                exclusions["England_additional_address_lines"] += 1
                continue
            admit(
                render(
                    f"gias:{r['URN']}",
                    "gb",
                    r["GOR (name)"],
                    [
                        ("street_address", r["Street"]),
                        ("city", r["Town"]),
                        ("postcode", r["Postcode"]),
                    ],
                    "england.csv",
                )
            )
    for r in json.loads((DATA / "ni.json").read_text())["result"]["records"]:
        admit(
            render(
                f"libraries-ni:{r['_id']}",
                "gb",
                "Northern Ireland",
                [
                    (
                        "street_address",
                        " ".join(str(r.get(k) or "").strip() for k in ("Number", "Street")),
                    ),
                    ("city", r["Town"]),
                    ("postcode", r["Postcode"]),
                ],
                "ni.json",
            )
        )
    selected = []
    for stratum, rows in sorted(pool.items()):
        count = 20 if stratum in states else 50
        if len(rows) < count:
            raise ValueError(f"Insufficient eligible addresses: {stratum}: {len(rows)} < {count}")
        selected.extend(
            sorted(rows, key=lambda r: hashlib.sha256((SEED + r["id"]).encode()).hexdigest())[
                :count
            ]
        )
    assert len(pool) == 61, sorted(pool)
    output = []
    for row in selected:
        output.append(dict(row, cohort="complete"))
        variant = render(
            row["id"] + ":no-postcode",
            row["country"],
            row["stratum"],
            [(p["label"], p["raw"]) for p in row["components"] if p["label"] != "postcode"],
            row["source"],
        )
        output.append(dict(variant, cohort="no-postcode"))
    PUBLIC.mkdir(parents=True, exist_ok=True)
    (PUBLIC / "inputs.json").write_text(json.dumps(output, indent=2, ensure_ascii=False))
    urls = json.loads((DATA / "source-urls.json").read_text())
    source_names = [*sorted(p.name for p in DATA.glob("fdic-*.json")), "england.csv", "ni.json"]
    manifest = dict(
        frozen_at=datetime.now(timezone.utc).isoformat(),
        seed=SEED,
        inputs_sha256=harness.sha(PUBLIC / "inputs.json"),
        preparation_sha256=harness.sha(Path(__file__)),
        model_sha256=harness.sha(ROOT / "packages/core/model.bin"),
        checkpoint_sha256=harness.sha(ROOT / "runs/ordered-h128-english-seven-20260916/best.pt"),
        sources={
            name: dict(url=urls[name], sha256=harness.sha(DATA / name)) for name in source_names
        },
        eligible={k: len(v) for k, v in pool.items()},
        exclusions=dict(exclusions),
        selected=dict(Counter(r["stratum"] for r in selected)),
        rows=len(output),
        entities=len(selected),
        labels="Source-provided fields; no parser or LLM-generated gold. Canonical comma-separated core-field rendering; organization names and optional UK counties omitted.",
        selection="20 per US state plus DC; 50 per English region plus 50 Northern Ireland libraries; SHA-256 ranking of seed + source ID; no prediction-based selection.",
        overlap="Exclude normalized street+city OR street+postcode matches in released-model training and previous Senzing/GeoSearch evaluations. Near matches and competitor overlap unknown.",
        metric="Exact per-field NFKC/casefold token multisets; case, commas, whitespace ignored; all other punctuation and token multiplicities retained. Extra fields fail. Micro field F1 also reported.",
        intervals="95% Wilson intervals for each cohort separately; complete and no-postcode share entities and must not be pooled as independent samples.",
        limitations="Author-run external-source diagnostic, not third-party verification. Structured institutional addresses, not natural user traffic. UK covers England and Northern Ireland only. Balanced strata are not population weights. Missing-postcode inputs are synthetic. No claims for Scotland or Wales.",
        models=json.loads((ROOT / "apps/website/public/benchmarks.json").read_text())["models"],
    )
    (DATA / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (PUBLIC / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(
        json.dumps(
            {k: manifest[k] for k in ("inputs_sha256", "selected", "exclusions", "entities")},
            indent=2,
        )
    )


def interval(correct, total):
    p, z = correct / total, 1.95996398454
    center = (p + z * z / (2 * total)) / (1 + z * z / total)
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / (1 + z * z / total)
    return [100 * (center - half), 100 * (center + half)]


def expand_robustness(rows, manifest):
    """User-requested protocol amendment; keep the original selected entities.

    Three models had run v1, but no predictions or scores were inspected before
    this amendment. Preserve v1's protocol and inputs rather than rewriting history.
    """
    if manifest.get("protocol_version") == 2:
        raise ValueError("Robustness protocol already frozen")
    (DATA / "inputs-v1.json").write_bytes((PUBLIC / "inputs.json").read_bytes())
    (PUBLIC / "protocol-v1.json").write_text(json.dumps(manifest, indent=2))
    result = []
    for row in rows:
        if row["cohort"] != "complete":
            continue
        result.append(row)
        for cohort in COHORTS[1:]:
            omitted = {
                "no-postcode": "postcode",
                "no-city": "city",
                "no-street": "street_address",
            }.get(cohort)
            values = [
                (p["label"], p["raw"].lower() if cohort == "lowercase" else p["raw"])
                for p in row["components"]
                if p["label"] != omitted
            ]
            separator = "\n" if cohort == "multiline" else " " if cohort == "no-commas" else ", "
            if cohort == "no-commas":
                values = [(label, raw.replace(",", "")) for label, raw in values]
            variant = render(
                row["id"] + ":" + cohort,
                row["country"],
                row["stratum"],
                values,
                row["source"],
                separator,
            )
            result.append(dict(variant, cohort=cohort))
    (PUBLIC / "inputs.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
    manifest: dict[str, Any] = dict(
        manifest,
        protocol_version=2,
        rows=len(result),
        inputs_sha256=harness.sha(PUBLIC / "inputs.json"),
        robustness_frozen_at=datetime.now(timezone.utc).isoformat(),
        robustness_code_sha256=harness.sha(Path(__file__)),
        cohorts=list(COHORTS),
        amendment="User rejected missing-postcode-only robustness after v1 inference began. Source entities and gold unchanged; no predictions or scores inspected before amendment. v1 protocol retained.",
        intervals="95% Wilson intervals within each cohort. All cohorts share the same entities; never pool them as independent samples.",
    )
    manifest["limitations"] = manifest["limitations"].replace(
        "Missing-postcode inputs are synthetic.",
        "All six robustness variants are synthetic and separately scored.",
    )
    (DATA / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (PUBLIC / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(
        json.dumps(
            dict(rows=len(result), entities=manifest["entities"], hash=manifest["inputs_sha256"])
        )
    )


def report(rows, manifest):
    from training.evaluate import field_tokens

    def score_fields(parts):
        values = field_tokens(parts)
        merged = defaultdict(Counter)
        for label, tokens in values.items():
            merged[manifest.get("field_projection", {}).get(label, label)].update(tokens)
        return dict(merged)

    predictions = {m: json.loads((DATA / f"{m}.json").read_text()) for m in MODELS}
    assert all(set(p) == {r["id"] for r in rows} for p in predictions.values())
    groups = []
    for country in ("us", "gb"):
        cohorts = list(manifest.get("cohorts", ("complete", "no-postcode")))
        if country == "gb" and manifest.get("protocol_version") == 4:
            cohorts += ["with-county", "without-county"]
        for cohort in cohorts:
            subset = [
                r
                for r in rows
                if r["country"] == country
                and (
                    r.get("has_county") is True
                    if cohort == "with-county"
                    else r.get("has_county") is False
                    if cohort == "without-county"
                    else r["cohort"] == cohort
                )
            ]
            counts = {}
            for model in MODELS:
                correct = tp = fp = fn = 0
                field_scores: dict[str, dict[str, float]] = defaultdict(
                    lambda: dict(rows=0, correct=0, predicted=0)
                )
                for row in subset:
                    gold, pred = (
                        score_fields(row["components"]),
                        score_fields(predictions[model][row["id"]]),
                    )
                    correct += pred == gold
                    for field in gold.keys() | pred.keys():
                        match = field in gold and field in pred and gold[field] == pred[field]
                        tp += match
                        fp += field in pred and not match
                        fn += field in gold and not match
                        field_scores[field]["predicted"] += field in pred
                        if field in gold:
                            field_scores[field]["rows"] += 1
                            field_scores[field]["correct"] += match
                for field in field_scores.values():
                    field["f1"] = 200 * field["correct"] / (field["rows"] + field["predicted"])
                counts[model] = dict(
                    correct=correct,
                    percent=100 * correct / len(subset),
                    interval=interval(correct, len(subset)),
                    field_f1=100 * 2 * tp / (2 * tp + fp + fn),
                    fields=dict(field_scores),
                )
            groups.append(dict(country=country, cohort=cohort, rows=len(subset), models=counts))
    result = dict(
        manifest=manifest,
        groups=groups,
        prediction_sha256={m: harness.sha(DATA / f"{m}.json") for m in MODELS},
    )
    (PUBLIC / "results.json").write_text(json.dumps(result, indent=2))
    for m in MODELS:
        (PUBLIC / f"{m}.json").write_bytes((DATA / f"{m}.json").read_bytes())
    print(json.dumps(groups, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "mode", choices=["prepare", "expand", "gpu", "libpostal", "senzing", "deep", "report"]
    )
    mode = ap.parse_args().mode
    if mode == "prepare":
        prepare()
    else:
        manifest = json.loads((DATA / "manifest.json").read_text())
        assert harness.sha(PUBLIC / "inputs.json") == manifest["inputs_sha256"]
        assert harness.sha(ROOT / "packages/core/model.bin") == manifest["model_sha256"]
        rows = json.loads((PUBLIC / "inputs.json").read_text())
        if mode == "expand":
            expand_robustness(rows, manifest)
        elif mode == "report":
            report(rows, manifest)
        else:
            if mode == "deep":
                predictions = harness.deep(rows)
                mode = "deepparse"
            elif mode == "gpu":
                predictions = harness.gpu(rows)
            else:
                predictions = harness.postal(rows, mode)
            (DATA / f"{mode}.json").write_text(json.dumps(predictions, indent=2))
