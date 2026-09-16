"""Deduplicate audited candidates globally; protect evaluation before admission.

Outputs remain staging, not semantically approved training data.
"""

import argparse
import gzip
import json
import sqlite3
from collections import Counter
from pathlib import Path

from .expand import file_sha256, street_keys
from .prepare import digest, group, identity


def rows(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            yield json.loads(line)


def source_entity(row):
    # Historical G-NAF source_entity_group held a street ID; use the actual source field.
    return (row.get("source_fields") or {}).get("address_detail_pid")


def consolidate(directory, output, protected):
    if not protected:
        raise ValueError("Explicit protected evaluation files are required")
    catalog = json.loads((directory / "inventory.json").read_text())
    inputs = []
    for country in catalog["countries"].values():
        for source in country["files"]:
            folder = directory / "audit" / source["path"].replace("/", "-")
            if not (folder / "report.json").exists():
                continue
            report = json.loads((folder / "report.json").read_text())
            if report["source"] != source:
                raise ValueError("Audit source differs from inventory")
            inputs.append((folder, report))
    if not inputs:
        raise ValueError("No completed audits")
    protection = [dict(path=str(p.resolve()), sha256=file_sha256(p)) for p in protected]
    output.mkdir(parents=True, exist_ok=False)
    counts = Counter()
    protected_legacy_streets = set()
    protected_entities = set()
    with sqlite3.connect((output / "identities.sqlite").resolve().as_uri(), uri=True) as db:
        db.execute("PRAGMA cache_size=-65536")
        db.execute("PRAGMA temp_store=FILE")
        db.executescript(
            "CREATE TABLE identities (text TEXT, signature TEXT, loose TEXT, "
            "model_input TEXT, model_labels TEXT, street TEXT, "
            "reason TEXT, emitted INTEGER DEFAULT 0, PRIMARY KEY(text, signature));"
            "CREATE TABLE protected (loose TEXT PRIMARY KEY);"
            "CREATE TABLE protected_streets (street TEXT PRIMARY KEY);"
        )
        for path in protected:
            for row in rows(path):
                row = dict(row, country=(row.get("country") or "").lower())
                db.execute("INSERT OR IGNORE INTO protected VALUES (?)", (identity(row["text"]),))
                db.execute("INSERT OR IGNORE INTO protected_streets VALUES (?)", (group(row),))
                protected_legacy_streets.update(street_keys(row))
                if entity := source_entity(row):
                    protected_entities.add(entity)
                counts["protected_rows"] += 1
        db.commit()
        for folder, report in inputs:
            uri = (folder / "identities.sqlite").resolve().as_uri() + "?mode=ro"
            db.execute("ATTACH DATABASE ? AS shard", (uri,))
            db.execute(
                "INSERT OR IGNORE INTO identities "
                "(text,signature,loose,model_input,model_labels,street) "
                "SELECT text,signature,loose,model_input,model_labels,street FROM shard.identities "
                "ORDER BY text,signature"
            )
            # A duplicate can carry another country's street group. Protect every occurrence.
            db.execute(
                "UPDATE identities SET reason='protected-overlap' WHERE (text,signature) IN "
                "(SELECT text,signature FROM shard.identities WHERE loose IN "
                "(SELECT loose FROM protected) OR street IN (SELECT street FROM protected_streets))"
            )
            db.commit()
            db.execute("DETACH DATABASE shard")
            # Audit indexes predate dual city/postcode protection; read original spans for both.
            for row in rows(folder / "candidates.jsonl.gz"):
                if (
                    street_keys(row) & protected_legacy_streets
                    or source_entity(row) in protected_entities
                ):
                    db.execute(
                        "UPDATE identities SET reason='protected-overlap' WHERE text=?",
                        (row["text"],),
                    )
            db.commit()
            counts["source_candidates"] += report["counts"].get("candidate_rows", 0)
            print(json.dumps(dict(indexed=report["source"]["path"])), flush=True)
        db.execute("CREATE INDEX model_inputs ON identities(model_input)")
        db.execute(
            "UPDATE identities SET reason='exact-label-conflict' WHERE reason IS NULL AND text IN "
            "(SELECT text FROM identities GROUP BY text HAVING COUNT(*)>1)"
        )
        db.execute(
            "UPDATE identities SET reason='model-input-label-conflict' WHERE reason IS NULL "
            "AND model_input IN (SELECT model_input FROM identities GROUP BY model_input "
            "HAVING COUNT(DISTINCT model_labels)>1)"
        )
        # Conservative historical exclusions, not duplicate identities or physical entities.
        db.execute(
            "UPDATE identities SET reason='protected-overlap' WHERE "
            "loose IN (SELECT loose FROM protected) OR street IN (SELECT street FROM protected_streets)"
        )
        # Protection follows identical model inputs even when only one source has an entity ID.
        db.execute(
            "UPDATE identities SET reason='protected-overlap' WHERE model_input IN "
            "(SELECT model_input FROM identities WHERE reason='protected-overlap')"
        )
        db.commit()
        counts["unique_text_label_pairs"] = db.execute(
            "SELECT COUNT(*) FROM identities"
        ).fetchone()[0]
        for reason, count in db.execute("SELECT reason,COUNT(*) FROM identities GROUP BY reason"):
            counts[reason or "retained_unique_candidates"] = count
        counts["duplicate_occurrences"] = (
            counts["source_candidates"] - counts["unique_text_label_pairs"]
        )
        with (
            gzip.open(output / "candidates.jsonl.gz", "xt", encoding="utf-8") as kept,
            gzip.open(output / "quarantine.jsonl.gz", "xt", encoding="utf-8") as quarantine,
        ):
            for folder, report in inputs:
                scanned = 0
                for row in rows(folder / "candidates.jsonl.gz"):
                    scanned += 1
                    if row["source_sha256"] != report["source"]["sha256"]:
                        raise ValueError("Candidate source hash differs from report")
                    signature = digest(json.dumps(row["components"], sort_keys=True))
                    entry = db.execute(
                        "SELECT reason,emitted FROM identities WHERE text=? AND signature=?",
                        (row["text"], signature),
                    ).fetchone()
                    if entry is None:
                        raise ValueError("Candidate missing from audit index")
                    if entry[1]:
                        continue
                    row["split"] = "staging"
                    row["annotation_status"] = "needs-semantic-review"
                    if entry[0]:
                        row["quarantine_reason"] = entry[0]
                    (quarantine if entry[0] else kept).write(
                        json.dumps(row, ensure_ascii=False) + "\n"
                    )
                    db.execute(
                        "UPDATE identities SET emitted=1 WHERE text=? AND signature=?",
                        (row["text"], signature),
                    )
                    if scanned % 4096 == 0:
                        db.commit()
                if scanned != report["counts"].get("candidate_rows", 0):
                    raise ValueError("Incomplete candidate stream")
                db.commit()
                print(
                    json.dumps(dict(completed=report["source"]["path"], rows=scanned)), flush=True
                )
        if db.execute("SELECT COUNT(*) FROM identities WHERE emitted=0").fetchone()[0]:
            raise ValueError("Unexported indexed candidates")
    result = dict(
        status="staging-only; semantic approval and final entity/split checks pending",
        counts=dict(counts),
        inputs=[
            dict(
                source=r["source"],
                audit_report_sha256=file_sha256(f / "report.json"),
                candidate_sha256=file_sha256(f / "candidates.jsonl.gz"),
            )
            for f, r in inputs
        ],
        protected=protection,
        code_sha256=file_sha256(Path(__file__)),
        limitations=[
            "Exact text plus exact labels deduplicated; normalized collisions are not merged",
            "All original occurrences and provenance remain in immutable input candidate streams",
            "Known G-NAF address-detail IDs protected across renderings; other entity equivalence remains incomplete",
            "Source domains cannot be recovered from this tagged source; no domain-disjoint claim",
            "Conflict decisions are not automatically applied; all conflicting variants quarantined",
        ],
    )
    (output / "report.json").write_text(json.dumps(result, indent=2))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--protected", type=Path, nargs="+", required=True)
    args = parser.parse_args(argv)
    print(json.dumps(consolidate(args.data, args.output, args.protected)), flush=True)
