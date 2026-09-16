"""Uncapped seven-country corpus from existing admitted originals; no source downloads."""

import argparse
import gzip
import json
import random
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict
from contextlib import ExitStack
from pathlib import Path

from gpu_postal.consolidate import rows
from gpu_postal.evaluate import field_tokens
from gpu_postal.expand import file_sha256, street_keys
from gpu_postal.prepare import digest, group, identity, write_rows
from gpu_postal.schema import seven_fields
from gpu_postal.tokenizer import components, encode

COUNTRIES = {"us", "gb", "au", "nz", "ca", "ie", "za"}
BASE = Path("data/latin-20260915/diagnostic-v4")
SUPPLEMENT = Path("data/latin-20260915/us-gb-expansion-v1/candidates.jsonl.gz")
PUBLIC = Path("data/multisource/public-benchmark.jsonl.gz")


def english(row):
    language = (row.get("language") or "").lower()
    return language in {"en", "eng"} or (
        not language and row.get("label_provenance") == "generated-from-fields"
    )


def split_for(key):
    bucket = int(digest("english-seven-v1|" + key)[:8], 16) % 100
    return "dev" if bucket < 5 else "test" if bucket < 10 else "train"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    base_manifest = json.loads((BASE / "manifest.json").read_text())
    balanced = json.loads(Path("data/latin-20260915/balanced-v5/manifest.json").read_text())
    inputs = [BASE / "train.jsonl.gz", SUPPLEMENT]
    for path in inputs:
        expected = balanced["inputs"][str(path.resolve())]
        if file_sha256(path) != expected:
            raise ValueError(f"Input changed: {path}")
    protected = [Path(p["path"]) for p in base_manifest["protected"]]
    protected.append(Path("data/competitor-comparison-20260916/inputs.jsonl"))
    texts, streets = set(), set()
    for path in protected:
        for row in rows(path):
            texts.add(identity(row["text"]))
            streets.update(street_keys(dict(row, country=(row.get("country") or "").lower())))
    counts, languages = Counter(), Counter()
    dbpath = args.output / "identities.sqlite"
    with (
        sqlite3.connect(dbpath) as db,
        sqlite3.connect(
            (BASE / "consolidated/identities.sqlite").resolve().as_uri() + "?mode=ro", uri=True
        ) as previous,
    ):
        db.execute("PRAGMA cache_size=-65536")
        db.execute(
            "CREATE TABLE rows (key TEXT PRIMARY KEY, signature TEXT, country TEXT, split TEXT, payload TEXT, conflict INTEGER DEFAULT 0)"
        )
        for source in inputs:
            for index, original in enumerate(rows(source), 1):
                country = original.get("country", "").lower()
                if country not in COUNTRIES:
                    continue
                counts["country_candidates"] += 1
                languages[country + "/" + str(original.get("language"))] += 1
                if not english(original):
                    counts["nonenglish_or_unknown"] += 1
                    continue
                if identity(original["text"]) in texts or street_keys(original) & streets:
                    counts["protected_overlap"] += 1
                    continue
                try:
                    row = seven_fields(dict(original, country=country))
                    item = encode(row)
                except ValueError:
                    counts["unrepresentable"] += 1
                    continue
                if item is None or components(item[1], item[2], row["text"]) != row["components"]:
                    counts["unrepresentable"] += 1
                    continue
                if source == SUPPLEMENT:
                    if original.get("annotation_status") != "accepted":
                        raise ValueError("Unapproved supplement row")
                    reasons = previous.execute(
                        "SELECT reason FROM identities WHERE model_input=?",
                        (digest(json.dumps(item[0])),),
                    ).fetchall()
                    if any(r[0] for r in reasons):
                        counts["historical_quarantine"] += 1
                        continue
                key = digest(
                    re.sub(
                        r"\s+", " ", unicodedata.normalize("NFKC", row["text"]).casefold()
                    ).strip()
                )
                signature = json.dumps(field_tokens(row["components"]), sort_keys=True)
                split = split_for(group(original))
                # Keep full original provenance in the immutable source files, not every epoch's spool.
                saved = {k: row[k] for k in ("id", "text", "country", "components")}
                saved.update(
                    language=row.get("language"),
                    source=row.get("source", row.get("source_sha256")),
                    split=split,
                    label_provenance=row.get("label_provenance"),
                )
                old = db.execute(
                    "SELECT signature,country FROM rows WHERE key=?", (key,)
                ).fetchone()
                if old:
                    counts["duplicates"] += 1
                    if old != (signature, country):
                        db.execute("UPDATE rows SET conflict=1 WHERE key=?", (key,))
                else:
                    db.execute(
                        "INSERT INTO rows VALUES (?,?,?,?,?,0)",
                        (key, signature, country, split, json.dumps(saved, ensure_ascii=False)),
                    )
                if index % 100000 == 0:
                    db.commit()
                    print(
                        json.dumps(dict(source=str(source), scanned=index, counts=dict(counts))),
                        flush=True,
                    )
            db.commit()
        counts["conflicting_keys"] = db.execute(
            "SELECT COUNT(*) FROM rows WHERE conflict=1"
        ).fetchone()[0]
        split_counts, source_counts = defaultdict(Counter), defaultdict(Counter)
        reservoirs = defaultdict(list)
        rng = random.Random(20260916)
        with ExitStack() as stack:
            outputs = {
                s: stack.enter_context(
                    gzip.open(
                        args.output / f"{s}{'-all' if s != 'train' else ''}.jsonl.gz",
                        "xt",
                        compresslevel=1,
                        encoding="utf-8",
                    )
                )
                for s in ("train", "dev", "test")
            }
            for country, split, payload in db.execute(
                "SELECT country,split,payload FROM rows WHERE conflict=0 ORDER BY rowid"
            ):
                row = json.loads(payload)
                outputs[split].write(payload + "\n")
                split_counts[split][country] += 1
                source_counts[country][row["source"] or "unknown"] += 1
                if split != "train":
                    key = (split, country)
                    pool = reservoirs[key]
                    seen = split_counts[split][country]
                    if len(pool) < 2000:
                        pool.append(row)
                    else:
                        replacement = rng.randrange(seen)
                        if replacement < 2000:
                            pool[replacement] = row
        evaluation_counts = {}
        for split in ("dev", "test"):
            sample = [r for c in sorted(COUNTRIES) for r in reservoirs[split, c]]
            if set(r["country"] for r in sample) != COUNTRIES:
                raise ValueError(f"Missing country in {split}; do not train")
            write_rows(args.output / f"{split}.jsonl.gz", sample)
            evaluation_counts[split] = dict(Counter(r["country"] for r in sample))
        write_rows(
            args.output / "public-benchmark.jsonl.gz",
            [r for r in rows(PUBLIC) if r.get("country", "").lower() in COUNTRIES],
        )
        manifest = dict(
            status="ready",
            countries=sorted(COUNTRIES),
            counts=dict(counts),
            language_counts=dict(languages),
            split_countries={k: dict(v) for k, v in split_counts.items()},
            evaluation_sample_countries=evaluation_counts,
            source_counts={k: dict(v) for k, v in source_counts.items()},
            inputs={str(p): file_sha256(p) for p in inputs + protected},
            code_sha256=file_sha256(Path(__file__)),
            outputs={p.name: file_sha256(p) for p in args.output.glob("*.gz")},
            split_policy="SHA256 street+city/postcode group: 90% train, 5% dev, 5% test; no training cap; evaluation reservoir <=2000/country/split, full heldout rows retained",
            limitations=[
                "All usable existing admitted originals, not every raw address shard or every address in each country.",
                "English source metadata or language-neutral generated fields; proper names retained, not automatic language certification.",
                "Same-source heldout streets, not independent natural traffic. Entity alias linkage incomplete.",
                "Legacy checkpoints may have seen these new source holdouts; scratch candidate has not.",
                "Public benchmark already inspected; diagnostic only, not training or epoch selection.",
                "Source mapping errors and source concentration remain; no population-wide accuracy claim.",
            ],
        )
        (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2))
        print(
            json.dumps(
                {
                    k: manifest[k]
                    for k in ("status", "counts", "split_countries", "evaluation_sample_countries")
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
