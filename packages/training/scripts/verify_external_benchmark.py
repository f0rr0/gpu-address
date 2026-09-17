"""Recompute public scores without importing the training scorer or dependencies."""

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from audit_website_benchmark import fields

PUBLIC = Path(__file__).resolve().parents[3] / "apps/website/public/evaluation"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--directory", default="evaluation-v4", choices=["evaluation", "evaluation-v3", "evaluation-v4"])
    public = PUBLIC.parent / ap.parse_args().directory
    manifest = json.loads((public / "manifest.json").read_text())
    report = json.loads((public / "results.json").read_text())
    raw = (public / "inputs.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == manifest["inputs_sha256"]
    rows = json.loads(raw)
    assert len(rows) == manifest["rows"]
    assert len({r["id"] for r in rows}) == len(rows)
    originals = [r for r in rows if r["cohort"] == "complete"]
    assert len(originals) == manifest["entities"]
    assert dict(Counter(r["stratum"] for r in originals)) == manifest["selected"]
    assert report["manifest"] == manifest
    def projected(parts):
        result = defaultdict(Counter)
        for label, tokens in fields(parts).items():
            result[manifest.get("field_projection", {}).get(label, label)].update(tokens)
        return dict(result)
    if manifest.get("protocol_version", 0) >= 3:
        assert manifest["field_projection"] == {"locality":"street_address", "district":"state"}
        assert set(manifest["cohorts"]) == {"complete"}
        for row in rows:
            source = row["source_fields"]
            if row["country"] == "gb":
                expected = [("street_address",source.get("RegAddress."+k,"")) for k in ("POBox","AddressLine1","AddressLine2")]
                expected += [("city",source["RegAddress.PostTown"])]
                if manifest["protocol_version"] >= 4:
                    expected += [("state",source.get("RegAddress.County",""))]
                expected += [("postcode",source["RegAddress.PostCode"])]
            else:
                sub = " ".join(f"{k} {source[k]}" for k in ("Building","Floor","Unit","Room") if source.get(k)) or source.get("SubAddress") or ""
                expected = [("street_address",f"{source['AddNo_Full']} {source['StNam_Full']} {sub}"), ("city",source["Post_City"]),("state",source["State"]),("postcode",source["Zip_Code"])]
            expected = [(k," ".join(v.split())) for k,v in expected if v.strip()]
            assert row["text"] == ", ".join(v for k,v in expected)
            assert [(p["label"],p["raw"]) for p in row["components"]] == expected
    by_id = {r["id"]: r for r in originals}
    for row in rows:
        assert all(row["text"][p["start"]:p["end"]] == p["raw"] for p in row["components"])
        if row["cohort"] != "complete":
            base = by_id[row["id"].rsplit(":", 1)[0]]
            expected = {p["label"]: p["raw"] for p in base["components"]}
            omitted = {"no-postcode": "postcode", "no-city": "city", "no-street": "street_address"}.get(row["cohort"])
            if omitted:
                del expected[omitted]
            elif row["cohort"] == "lowercase":
                expected = {k: v.lower() for k, v in expected.items()}
            elif row["cohort"] == "no-commas":
                expected = {k: " ".join(v.replace(",", "").split()) for k, v in expected.items()}
            assert {p["label"]: p["raw"] for p in row["components"]} == expected
    for model, expected_hash in report["prediction_sha256"].items():
        raw = (public / f"{model}.json").read_bytes()
        assert hashlib.sha256(raw).hexdigest() == expected_hash
        pred = json.loads(raw)
        assert set(pred) == {r["id"] for r in rows}
        for group in report["groups"]:
            subset = [r for r in rows if r["country"] == group["country"] and (
                r.get("has_county") is True if group["cohort"] == "with-county" else
                r.get("has_county") is False if group["cohort"] == "without-county" else
                r["cohort"] == group["cohort"])]
            assert len(subset) == group["rows"]
            correct = matches = predicted_fields = gold_fields = 0
            breakdown = defaultdict(Counter)
            for row in subset:
                actual, gold = projected(pred[row["id"]]), projected(row["components"])
                correct += actual == gold
                for label in actual.keys() | gold.keys():
                    breakdown[label]["rows"] += label in gold
                    breakdown[label]["predicted"] += label in actual
                    breakdown[label]["correct"] += label in actual and label in gold and actual[label] == gold[label]
                matches += sum(k in actual and actual[k] == v for k, v in gold.items())
                predicted_fields += len(actual)
                gold_fields += len(gold)
            score = group["models"][model]
            assert correct == score["correct"]
            for label, counts in breakdown.items():
                for name, value in counts.items():
                    if name in score["fields"].get(label, {}):
                        assert score["fields"][label][name] == value
                if "f1" in score["fields"].get(label, {}):
                    assert abs(score["fields"][label]["f1"] - 200*counts["correct"]/(counts["rows"]+counts["predicted"])) < 1e-10
            assert abs(score["percent"] - 100*correct/len(subset)) < 1e-10
            assert abs(score["field_f1"] - 200*matches/(predicted_fields+gold_fields)) < 1e-10
            n, z = len(subset), 1.95996398454
            rate = correct/n
            center = (rate+z*z/(2*n))/(1+z*z/n)
            radius = z*math.sqrt(rate*(1-rate)/n+z*z/(4*n*n))/(1+z*z/n)
            assert all(abs(a-b)<1e-9 for a,b in zip(score["interval"], [100*(center-radius),100*(center+radius)]))
    if manifest.get("protocol_version") == 4:
        parity = json.loads((public / "browser-parity.json").read_text())
        assert parity["status"] == "passed" and not parity["differences"]
        assert parity["rows"] == len(rows)
        assert parity["inputsSha256"] == manifest["inputs_sha256"]
        assert parity["modelSha256"] == manifest["model_sha256"]
    print(f"Verified {len(rows):,} inputs, {len(originals):,} source entities, prediction hashes, confidence intervals, and published overall/per-field scores.")


if __name__ == "__main__":
    main()
