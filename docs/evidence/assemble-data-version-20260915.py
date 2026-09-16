"""Assemble an uncapped provisional diagnostic corpus; never start training.

PYTHONPATH=packages/training/src python docs/evidence/assemble-data-version-20260915.py --output data/latin-20260915/diagnostic-v1
All input reports must be complete. Existing outputs are never overwritten.
"""

import argparse
import gzip
import json
import runpy
import sqlite3
from collections import Counter
from contextlib import ExitStack
from pathlib import Path

from gpu_postal.consolidate import consolidate, rows, source_entity
from gpu_postal.corpus import address_type
from gpu_postal.expand import file_sha256
from gpu_postal.prepare import digest, group, identity, validate
from gpu_postal.tokenizer import components, encode

DATA = Path("data/latin-20260915")
EVIDENCE = Path("docs/evidence")
PINS = {
    EVIDENCE
    / "nz-za-partition-review-20260915.json": "22c1e50b0f356b35a6003a2d59d3842caca70f608314bf82a9cc33495d40293e",
    EVIDENCE
    / "gnaf-full-audit-20260915-v3.json": "3487bf4f58fbc94b1ddb4a198cb242c1ea75663ac9cefe5f206750e37aceba26",
    DATA
    / "curated-v2/manifest.json": "7cf1db0367b3a01f87f3a45076df8714dd0444aaa7cfb5011602ebddb86417d7",
    DATA
    / "curated-v2/train.jsonl.gz": "6bc7616b58e572f3f84d57de755d0c18f66855257541cd88ea19781df993d14b",
}
PROTECTED = [
    Path("data/multisource") / name
    for name in ["public-benchmark.jsonl.gz", "dev.jsonl.gz", "source-dev.jsonl.gz"]
] + [
    Path("data/webgpu/dev.jsonl.gz"),
    EVIDENCE / "natural-ai-review.jsonl",
    EVIDENCE / "natural-complete-ai-review.jsonl",
    DATA / "natural-v1/dev.jsonl.gz",
    DATA / "natural-v1/test.jsonl.gz",
]


def check(path, expected=None):
    actual = file_sha256(path)
    if expected is not None and actual != expected:
        raise ValueError(f"Changed approval/input boundary: {path}")
    return dict(path=str(path.resolve()), sha256=actual)


def index_row(db, row, item):
    labels = {c["label"] for c in row["components"]}
    street = group(row) if "road" in labels and labels & {"city", "postcode"} else None
    db.execute(
        "INSERT OR IGNORE INTO identities VALUES (?,?,?,?,?,?)",
        (
            row["text"],
            digest(json.dumps(row["components"], sort_keys=True)),
            identity(row["text"]),
            digest(json.dumps(item[0])),
            digest(json.dumps(item[1])),
            street,
        ),
    )
    return street


def selfcheck():
    row = dict(
        text="12 Main Road",
        country="au",
        components=[
            dict(label="house_number", raw="12", start=0, end=2),
            dict(label="road", raw="Main Road", start=3, end=12),
        ],
    )
    validate(row)
    item = encode(row)
    assert item is not None and components(item[1], item[2], row["text"]) == row["components"]
    with sqlite3.connect(":memory:") as db:
        db.execute(
            "CREATE TABLE identities (text TEXT, signature TEXT, loose TEXT, model_input TEXT, model_labels TEXT, street TEXT, PRIMARY KEY(text,signature))"
        )
        index_row(db, row, item)
        index_row(db, row, item)
        assert db.execute("SELECT COUNT(*) FROM identities").fetchone()[0] == 1
    assert len(PROTECTED) == 8
    print("Adapter index/span/protected-set selfcheck passed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--selfcheck", action="store_true")
    args = parser.parse_args()
    if args.selfcheck:
        return selfcheck()
    if args.output is None:
        parser.error("--output required")
    inputs = [check(p, h) for p, h in PINS.items()]
    approval = json.loads((EVIDENCE / "nz-za-partition-review-20260915.json").read_text())
    inputs += [check(Path(i["path"]), i["sha256"]) for i in approval["inputs"]]
    curated = json.loads((DATA / "curated-v2/manifest.json").read_text())
    curated_hashes = {i["path"]: i["sha256"] for i in curated["inputs"]}
    protected = [check(p, curated_hashes[str(p.resolve())]) for p in PROTECTED]
    gnaf_review = json.loads((EVIDENCE / "gnaf-full-audit-20260915-v3.json").read_text())
    uncertain = {
        r["id"] for r in gnaf_review["semantic_review"]["tail_inspection"]["needs_adjudication"]
    }
    assert len(uncertain) == 6
    folders = [DATA / "audit" / f"{c}-chunk-0.parquet" for c in ["nz", "za"]]
    folders.append(DATA / "structured-v2/audit/au-gnaf-2022-shard0.parquet")
    reports = [json.loads((f / "report.json").read_text()) for f in folders]
    if reports[-1]["source"]["sha256"] != gnaf_review["audit"]["source_sha256_verified"]:
        raise ValueError("GNAF review/source mismatch")
    if reports[-1]["code_sha256"]["expand.py"] != gnaf_review["audit"]["mapper_sha256"]:
        raise ValueError("GNAF mapper changed since reviewed full scan")
    for f in folders:
        inputs += [
            check(f / n)
            for n in [
                "report.json",
                "candidates.jsonl.gz",
                "excluded.jsonl.gz",
                "identities.sqlite",
            ]
        ]
    global_folder = DATA / "consolidated-v2"
    inputs += [check(global_folder / n) for n in ["report.json", "identities.sqlite"]]
    with sqlite3.connect(
        (global_folder / "identities.sqlite").resolve().as_uri() + "?mode=ro", uri=True
    ) as original:
        global_text_conflicts = {
            r[0]
            for r in original.execute("SELECT text FROM identities GROUP BY text HAVING COUNT(*)>1")
        }
        global_model_conflicts = {
            r[0]
            for r in original.execute(
                "SELECT model_input FROM identities GROUP BY model_input HAVING COUNT(DISTINCT model_labels)>1"
            )
        }
    partition = runpy.run_path(str(EVIDENCE / "sample-nz-za-partitions-20260915.py"))["partition"]
    args.output.mkdir(parents=True, exist_ok=False)
    staging = args.output / "approved-staging"
    staging.mkdir()
    catalog = json.loads((DATA / "inventory.json").read_text())
    countries = {k: dict(name=v["name"], files=[]) for k, v in catalog["countries"].items()}
    assert len(countries) == 249
    counts, buckets = Counter(), {}
    approved_countries, original_countries = Counter(), Counter()
    with ExitStack() as stack:
        quarantine = stack.enter_context(
            gzip.open(args.output / "approval-quarantine.jsonl.gz", "xt", encoding="utf-8")
        )

        def stage(row, evidence, reason=None):
            counts["input_occurrences"] += 1
            country = row["country"].lower()
            original_countries[country] += 1
            if reason:
                row["quarantine_reason"] = reason
                quarantine.write(json.dumps(row, ensure_ascii=False) + "\n")
                counts["approval-quarantine:" + reason] += 1
                return
            validate(row)
            item = encode(row)
            if item is None or components(item[1], item[2], row["text"]) != row["components"]:
                raise ValueError("Approved row failed mechanical checks")
            conflict = (
                "known-global-exact-label-conflict"
                if row["text"] in global_text_conflicts
                else "known-global-model-input-label-conflict"
                if digest(json.dumps(item[0])) in global_model_conflicts
                else None
            )
            if conflict:
                row["quarantine_reason"] = conflict
                quarantine.write(json.dumps(row, ensure_ascii=False) + "\n")
                counts["approval-quarantine:" + conflict] += 1
                return
            approved_countries[country] += 1
            key = country + "/" + row["source_sha256"] + ".approved"
            if key not in buckets:
                folder = staging / "audit" / key.replace("/", "-")
                folder.mkdir(parents=True)
                source = dict(
                    path=key,
                    sha256=row["source_sha256"],
                    format="approved-jsonl",
                    source_family=row.get(
                        "source_family", "gnaf-2022" if country == "au" else "deepparse-worldwide"
                    ),
                )
                countries[country]["files"].append(source)
                db = stack.enter_context(sqlite3.connect(folder / "identities.sqlite"))
                db.execute("PRAGMA cache_size=-65536")
                db.execute("PRAGMA temp_store=FILE")
                db.execute(
                    "CREATE TABLE identities (text TEXT, signature TEXT, loose TEXT, model_input TEXT, model_labels TEXT, street TEXT, PRIMARY KEY(text,signature))"
                )
                db.execute(
                    "CREATE TABLE source_groups (kind TEXT, value TEXT, PRIMARY KEY(kind,value))"
                )
                stream = stack.enter_context(
                    gzip.open(folder / "candidates.jsonl.gz", "xt", encoding="utf-8")
                )
                buckets[key] = dict(db=db, stream=stream, folder=folder, source=source, count=0)
            bucket = buckets[key]
            street = index_row(bucket["db"], row, item)
            entity = source_entity(row)
            kind, value = (
                ("gnaf-address-detail-id", entity)
                if entity
                else (
                    ("atp-snapshot-group", row["entity_group"])
                    if row.get("entity_group")
                    else ("tagged-street-not-entity", street)
                )
            )
            if value:
                bucket["db"].execute(
                    "INSERT OR IGNORE INTO source_groups VALUES (?,?)", (kind, value)
                )
            row.update(
                mapping_review=evidence,
                mapping_status="provisional-diagnostic",
                split="staging",
                source_annotation_status=row.get("annotation_status"),
            )
            bucket["stream"].write(json.dumps(row, ensure_ascii=False) + "\n")
            bucket["count"] += 1
            if bucket["count"] % 4096 == 0:
                bucket["db"].commit()

        for row in rows(DATA / "curated-v2/train.jsonl.gz"):
            stage(row, "data/latin-20260915/curated-v2/manifest.json")
        for country, folder, report in zip(["nz", "za", "au"], folders, reports):
            with sqlite3.connect(
                (folder / "identities.sqlite").resolve().as_uri() + "?mode=ro", uri=True
            ) as original:
                conflicts = (
                    {
                        r[0]
                        for r in original.execute(
                            "SELECT text FROM identities GROUP BY text HAVING COUNT(*)>1"
                        )
                    }
                    if country != "au"
                    else set()
                )
            scanned = 0
            for row in rows(folder / "candidates.jsonl.gz"):
                scanned += 1
                if row["source_sha256"] != report["source"]["sha256"]:
                    raise ValueError("Candidate/source mismatch")
                if country == "au":
                    reason = "known-composite-premise" if source_entity(row) in uncertain else None
                    evidence = str(EVIDENCE / "gnaf-full-audit-20260915-v3.json")
                else:
                    selected = partition(row, conflicts)
                    allowed = (
                        {"number-road", "road-partial"} if country == "nz" else {"number-road"}
                    )
                    reason = (
                        None if selected in allowed else "unapproved-" + country + "-" + selected
                    )
                    evidence = str(EVIDENCE / "nz-za-partition-review-20260915.json")
                stage(row, evidence, reason)
                if scanned % 100000 == 0:
                    print(f"staged {country}: {scanned:,} source occurrences", flush=True)
            if scanned != report["counts"]["candidate_rows"]:
                raise ValueError("Incomplete source candidate stream")
        for bucket in buckets.values():
            bucket["db"].commit()
            bucket["source_groups"] = dict(
                bucket["db"].execute("SELECT kind,COUNT(*) FROM source_groups GROUP BY kind")
            )
    for bucket in buckets.values():
        (bucket["folder"] / "report.json").write_text(
            json.dumps(dict(source=bucket["source"], counts=dict(candidate_rows=bucket["count"])))
        )
    (staging / "inventory.json").write_text(json.dumps(dict(countries=countries)))
    result = consolidate(staging, args.output / "consolidated", PROTECTED)
    coverage: dict = {
        c: dict(
            name=v["name"],
            training_rows=0,
            address_types={},
            status="missing-approved-coverage",
            input_source_occurrences=original_countries[c],
            approved_source_occurrences=approved_countries[c],
        )
        for c, v in countries.items()
    }
    with gzip.open(args.output / "train.jsonl.gz", "xt", encoding="utf-8") as train:
        for row in rows(args.output / "consolidated/candidates.jsonl.gz"):
            row.update(
                split="train",
                annotation_status="accepted-for-provisional-diagnostic",
                mapping_status="provisional-diagnostic",
                training_admission=True,
                evaluation_eligible=False,
            )
            train.write(json.dumps(row, ensure_ascii=False) + "\n")
            entry = coverage[row["country"].lower()]
            entry["training_rows"] += 1
            kind = address_type(row)
            entry["address_types"][kind] = entry["address_types"].get(kind, 0) + 1
            entry["status"] = "partial-provisional-coverage"
    (args.output / "coverage.json").write_text(json.dumps(coverage, indent=2))
    manifest = dict(
        status="completed-provisional-diagnostic-no-training-run",
        inputs=inputs,
        protected=protected,
        natural_evaluation=curated["natural_evaluation"],
        training_exposure="No training or sampler run/configured; retained full approved occurrence distribution is reported separately from future training exposure. No per-country caps or synthetic variants.",
        approval_counts=dict(counts),
        prior_global_conflict_groups=dict(
            text=len(global_text_conflicts), model_input=len(global_model_conflicts)
        ),
        consolidation=result,
        approved_source_groups={k: b["source_groups"] for k, b in buckets.items()},
        training_rows=sum(v["training_rows"] for v in coverage.values()),
        source_domain_aliases=curated["source_domain_aliases"],
        prior_curated_decisions=str(DATA / "curated-v2/decisions.jsonl.gz"),
        code_sha256=file_sha256(Path(__file__)),
        outputs={
            n: file_sha256(args.output / n)
            for n in ["train.jsonl.gz", "coverage.json", "approval-quarantine.jsonl.gz"]
        },
        limitations=[
            "Source mapping reviews are samples, not individual AI labels for NZ/ZA/GNAF or semantic certification.",
            "Original label_provenance preserved; no synthetic variants or historical training merge.",
            "All duplicate occurrences/aliases survive in approved-staging and original input streams; consolidate emits first identical text/labels.",
            "Known GNAF IDs protected; other physical-entity equivalence and hidden composites remain incomplete.",
            "Known exact/model label conflicts across the full prior 14-source audit remain quarantined even when competing annotations are outside approved partitions; new global conflicts are also checked across approved streams.",
            "Original audit exclusions and unapproved remainder remain retained, not declared invalid.",
            "Only a bounded source selection has approval; all249-country deficits remain explicit.",
        ],
    )
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(dict(training_rows=manifest["training_rows"], completed=str(args.output))))


if __name__ == "__main__":
    main()
