"""Worldwide source inventory and uncapped, disk-backed candidate audit.

This stages originals, not training-ready labels or a new evaluation split.
"""

import argparse
import gzip
import json
import random
import re
import resource
import sqlite3
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from .expand import HF_REV, acquire, file_sha256, gnaf_row, hf_row
from .prepare import digest, group, identity, validate
from .tokenizer import components, encode

DATASET = "https://huggingface.co/datasets/deepparse/worldwide-addresses"
TREE = f"https://huggingface.co/api/datasets/deepparse/worldwide-addresses/tree/{HF_REV}"
COUNTRY_CODES = (
    "https://raw.githubusercontent.com/pycountry/pycountry/24.6.1/"
    "src/pycountry/databases/iso3166-1.json"
)
# PyArrow's RE2 Unicode scripts: Latin plus shared punctuation/digits/combining marks.
# This is script eligibility, not English-language detection or postal validation.
LATIN = r"^[\p{Latin}\p{Common}\p{Inherited}]*$"


def inventory(directory):
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / "inventory.json"
    if output.exists():
        raise ValueError("Inventory exists; reuse it or choose a new data directory")
    entries, pages = [], []
    url = TREE + "?recursive=true&limit=1000"
    while url:
        if not url.startswith(TREE + "?") or url in pages:
            raise ValueError("Unexpected inventory pagination URL")
        with urllib.request.urlopen(url, timeout=30) as response:
            entries.extend(json.load(response))
            pages.append(url)
            following = re.search(r'<([^>]+)>;\s*rel="next"', response.headers.get("Link", ""))
            url = following[1] if following else None
    with urllib.request.urlopen(COUNTRY_CODES, timeout=30) as response:
        country_bytes = response.read()
    countries = {
        row["alpha_2"].lower(): dict(name=row["name"], files=[])
        for row in json.loads(country_bytes)["3166-1"]
    }
    paths = set()
    for entry in entries:
        path = entry["path"]
        if not path.endswith(".parquet"):
            continue
        match = re.fullmatch(r"([a-z]{2})/chunk-[0-9]+\.parquet", path)
        if not match or path in paths:
            raise ValueError("Unexpected or duplicate source path: " + path)
        paths.add(path)
        sha = entry.get("lfs", {}).get("oid", "")
        if not re.fullmatch(r"[0-9a-f]{64}", sha) or entry["size"] <= 0:
            raise ValueError("Missing source integrity metadata: " + path)
        countries.setdefault(match[1], dict(name=match[1], files=[]))["files"].append(
            dict(path=path, bytes=entry["size"], sha256=sha)
        )
    result = dict(
        revision=HF_REV,
        dataset=DATASET,
        source_family="libpostal-derived; not independent of related tagged corpora",
        label_status="source tags; semantic mapping not certified",
        license="Dataset card: CC-BY-4.0; retain upstream lineage and review reuse terms",
        country_reference=dict(url=COUNTRY_CODES, sha256=digest(country_bytes.decode())),
        pages=pages,
        retrieved_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        countries=dict(sorted(countries.items())),
    )
    with output.open("x") as stream:
        json.dump(result, stream, indent=2)
    return coverage(directory)


def coverage(directory):
    catalog = json.loads((directory / "inventory.json").read_text())
    rows: dict[str, dict] = {}
    for country, entry in catalog["countries"].items():
        reports = []
        for source in entry["files"]:
            report = directory / "audit" / source["path"].replace("/", "-") / "report.json"
            if report.exists():
                result = json.loads(report.read_text())
                if result["source"]["sha256"] != source["sha256"]:
                    raise ValueError("Audit does not match inventory")
                reports.append(result)
        counts = Counter()
        for report in reports:
            counts.update(report["counts"])
        rows[country] = dict(
            name=entry["name"],
            available_shards=len(entry["files"]),
            available_bytes=sum(f["bytes"] for f in entry["files"]),
            audited_shards=len(reports),
            status="no-source"
            if not entry["files"]
            else ("audited" if len(reports) == len(entry["files"]) else "not-fully-audited"),
            counts=dict(counts) if reports else None,
        )
    result = dict(
        scope="pinned worldwide source inventory; unscanned counts unknown, not zero",
        countries=rows,
        available_shards=sum(r["available_shards"] for r in rows.values()),
        available_bytes=sum(r["available_bytes"] for r in rows.values()),
        audited_shards=sum(r["audited_shards"] for r in rows.values()),
    )
    temporary = directory / "coverage.tmp"
    temporary.write_text(json.dumps(result, indent=2))
    temporary.replace(directory / "coverage.json")
    return result


def source_file(directory, source, cache=None):
    name = "worldwide-" + source["path"].split("/")[0]
    if cache and source["path"].endswith("/chunk-0.parquet"):
        cached = cache / (name + ".raw")
        if cached.exists() and file_sha256(cached) == source["sha256"]:
            return cached
    raw = directory / "raw"
    raw.mkdir(exist_ok=True)
    name = source["path"].replace("/", "-")
    url = f"{DATASET}/resolve/{HF_REV}/{source['path']}"
    record = acquire((name, (url, source["bytes"], False)), raw)
    if record["status"] != "acquired":
        raise ValueError("Source acquisition failed: " + record.get("error", name))
    if record["sha256"] != source["sha256"] or record["bytes"] != source["bytes"]:
        raise ValueError("Source bytes/hash do not match pinned inventory: " + name)
    return raw / (name + ".raw")


def address_type(row):
    labels = {s["label"] for s in row["components"]}
    if labels & {"unit", "level", "house", "staircase", "entrance"}:
        return "building-unit-floor"
    if "po_box" in labels:
        return "po-box"
    if {"house_number", "road"} <= labels:
        return "number-and-road"
    if "road" in labels:
        return "road-without-number"
    if labels & {"house_number", "near", "category"}:
        return "other-partial"
    return "administrative-only"


def audit_file(path, source, output):
    """Retain every structurally valid Latin row; count collisions without merging them."""
    source_format = source.get("format", "hf")
    if source_format not in {"hf", "gnaf"}:
        raise ValueError(f"Unsupported audit source format: {source_format}")
    if file_sha256(path) != source["sha256"]:
        raise ValueError("Audit source checksum mismatch")
    output.mkdir(parents=True, exist_ok=False)
    counts, labels, types = Counter(), Counter(), Counter()
    samples, sample_seen, rng = defaultdict(list), Counter(), random.Random(20260915)
    started = time.monotonic()
    country = "au" if source_format == "gnaf" else source["path"].split("/")[0]
    source_parquet = pq.ParquetFile(path)
    with (
        sqlite3.connect(output / "identities.sqlite") as db,
        gzip.open(output / "candidates.jsonl.gz", "xt", encoding="utf-8") as candidates,
        gzip.open(output / "excluded.jsonl.gz", "xt", encoding="utf-8") as excluded,
    ):
        db.execute("PRAGMA cache_size=-8192")
        db.execute("PRAGMA temp_store=FILE")
        db.execute(
            "CREATE TABLE identities (text TEXT, signature TEXT, loose TEXT, "
            "model_input TEXT, model_labels TEXT, street TEXT, "
            "PRIMARY KEY (text, signature))"
        )
        for batch in source_parquet.iter_batches(batch_size=4096):
            records = batch.to_pylist()
            rendered, render_errors = [], []
            if source_format == "gnaf":
                for record in records:
                    try:
                        rendered.append(gnaf_row(record))
                        render_errors.append(None)
                    except (ValueError, AssertionError, KeyError, TypeError) as error:
                        rendered.append(None)
                        render_errors.append(str(error) or type(error).__name__)
                texts = pa.array(
                    [row["text"] if row else None for row in rendered], type=pa.string()
                )
            else:
                texts = batch.column("Address")
            latin = pc.call_function(
                "match_substring_regex", [texts], pc.MatchSubstringOptions(LATIN)
            ).to_pylist()
            for position, (record, in_scope) in enumerate(zip(records, latin)):
                index = counts["raw_rows"]
                counts["raw_rows"] += 1
                row = rendered[position] if rendered else None
                reason = render_errors[position] if render_errors else None
                reason = reason or ("non-latin-script" if not in_scope else None)
                counts["latin_rows"] += bool(in_scope)
                try:
                    if reason:
                        raise ValueError(reason)
                    if source_format == "hf":
                        row = hf_row(record, country)
                    assert row is not None
                    validate(row)
                    kind = address_type(row)
                    types[kind] += 1
                    labels.update(s["label"] for s in row["components"])
                    item = encode(row)
                    if item is None:
                        raise ValueError("input-limits-or-empty")
                    if components(item[1], item[2], row["text"]) != item[3]["components"]:
                        raise ValueError("tokenizer-cannot-represent-spans")
                except (ValueError, AssertionError, KeyError, TypeError) as error:
                    reason = str(error) or type(error).__name__
                ref = dict(source_path=source["path"], source_row=index)
                if reason:
                    counts["excluded:" + reason] += 1
                    review = dict(**ref, reason=reason, source_record=record)
                    excluded.write(json.dumps(review, ensure_ascii=False) + "\n")
                    bucket = "excluded:" + reason
                else:
                    assert row is not None and item is not None
                    row.update(
                        **ref,
                        id=source["sha256"] + ":" + str(index),
                        source_sha256=source["sha256"],
                        annotation_status="needs-semantic-review",
                        split="staging",
                    )
                    # Street groups are diagnostics, never physical entity IDs or admission caps.
                    fields = {s["label"] for s in row["components"]}
                    street = (
                        group(row) if "road" in fields and fields & {"city", "postcode"} else None
                    )
                    db.execute(
                        "INSERT OR IGNORE INTO identities VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            row["text"],
                            digest(json.dumps(row["components"], sort_keys=True)),
                            identity(row["text"]),
                            digest(json.dumps(item[0])),
                            digest(json.dumps(item[1])),
                            street,
                        ),
                    )
                    candidates.write(json.dumps(row, ensure_ascii=False) + "\n")
                    counts["candidate_rows"] += 1
                    counts["candidate:" + kind] += 1
                    review, bucket = row, "candidate:" + kind
                # Sampling is ONLY for manual/AI inspection, never corpus admission.
                sample_seen[bucket] += 1
                if len(samples[bucket]) < 20:
                    samples[bucket].append(review)
                else:
                    position = rng.randrange(sample_seen[bucket])
                    if position < 20:
                        samples[bucket][position] = review
            db.commit()
        if counts["raw_rows"] != source_parquet.metadata.num_rows:
            raise ValueError("Incomplete source scan")
        summary = {
            "unique_texts": "SELECT COUNT(DISTINCT text) FROM identities",
            "unique_text_label_pairs": "SELECT COUNT(*) FROM identities",
            "street_groups_not_entities": "SELECT COUNT(DISTINCT street) FROM identities",
            "conflicting_exact_texts": "SELECT COUNT(*) FROM (SELECT text FROM identities "
            "GROUP BY text HAVING COUNT(*) > 1)",
            "lossy_keys_with_multiple_texts": "SELECT COUNT(*) FROM (SELECT loose FROM identities "
            "GROUP BY loose HAVING COUNT(DISTINCT text) > 1)",
            "conflicting_model_inputs": "SELECT COUNT(*) FROM (SELECT model_input FROM identities "
            "GROUP BY model_input HAVING COUNT(DISTINCT model_labels) > 1)",
        }
        identities = {key: db.execute(sql).fetchone()[0] for key, sql in summary.items()}
    result = dict(
        source=source,
        source_format=source_format,
        country=country,
        counts=dict(counts),
        fields=dict(labels),
        latin_mapped_types=dict(types),
        identities=identities,
        elapsed_s=round(time.monotonic() - started, 2),
        peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        * (1 if sys.platform == "darwin" else 1024),
        pyarrow=pa.__version__,
        script_filter=LATIN,
        script_filter_input="successfully rendered structured rows; mapping failures have no rendered text"
        if source_format == "gnaf"
        else "original Address field",
        code_sha256={
            p.name: file_sha256(p)
            for p in (
                Path(__file__),
                Path(__file__).with_name("expand.py"),
                Path(__file__).with_name("prepare.py"),
                Path(__file__).with_name("tokenizer.py"),
            )
        },
        status="staging-only: semantic review, deduplication and evaluation exclusion pending",
        limitations=[
            "All candidates retained, including duplicates and conflicting annotations",
            "Structured source entity/street IDs and fields retained; text/street indexes are not entity deduplication"
            if source_format == "gnaf"
            else "No physical entity IDs in this tagged source; unique texts are not unique premises",
            "Identity counts are per shard, not globally deduplicated",
            "Lossy-key collisions include harmless variants as well as possible false merges",
            "Review samples are stratified convenience samples, not semantic accuracy estimates",
        ]
        + (
            [
                "G-NAF inputs are rendered from fields, not untouched natural text; source-version and reuse terms apply"
            ]
            if source_format == "gnaf"
            else []
        ),
    )
    (output / "review.json").write_text(json.dumps(samples, ensure_ascii=False, indent=2))
    # A report is the completion marker; interrupted/failed directories must not be reused.
    (output / "report.json").write_text(json.dumps(result, indent=2))
    return result


def conflicts(output):
    """Extract all annotations of per-shard conflicting texts, without choosing a winner."""
    report = json.loads((output / "report.json").read_text())
    with sqlite3.connect(
        (output / "identities.sqlite").resolve().as_uri() + "?mode=ro", uri=True
    ) as db:
        texts = {
            row[0]
            for row in db.execute("SELECT text FROM identities GROUP BY text HAVING COUNT(*) > 1")
        }
    if len(texts) != report["identities"]["conflicting_exact_texts"]:
        raise ValueError("Conflict index does not match completed audit")
    count, seen = 0, set()
    with (
        gzip.open(output / "candidates.jsonl.gz", "rt", encoding="utf-8") as source,
        gzip.open(output / "conflicts.jsonl.gz", "xt", encoding="utf-8") as target,
    ):
        for line in source:
            row = json.loads(line)
            if row["text"] in texts:
                target.write(line)
                seen.add(row["text"])
                count += 1
    if seen != texts:
        raise ValueError("Candidate stream is missing indexed conflict texts")
    return dict(
        source=report["source"],
        conflicting_texts=len(texts),
        rows=count,
        status="review-only; duplicates retained; cross-shard conflicts not included",
    )


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=["inventory", "audit", "coverage", "conflicts"])
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument(
        "--countries", nargs="+", help="Explicit audit/download scope; all their shards"
    )
    ap.add_argument("--cache", type=Path, help="Reuse checksum-matched old raw files read-only")
    args = ap.parse_args(argv)
    if args.action == "inventory":
        result = inventory(args.data)
    elif args.action == "coverage":
        result = coverage(args.data)
    else:
        catalog = json.loads((args.data / "inventory.json").read_text())
        if catalog["revision"] != HF_REV:
            raise ValueError("Inventory revision differs from source mapper")
        if not args.countries or set(args.countries) - catalog["countries"].keys():
            ap.error("Specify valid inventory country codes with --countries")
        for country in dict.fromkeys(args.countries):
            for source in catalog["countries"][country]["files"]:
                output = args.data / "audit" / source["path"].replace("/", "-")
                if args.action == "conflicts":
                    print(json.dumps(conflicts(output)), flush=True)
                    continue
                if (output / "report.json").exists():
                    continue
                if output.exists():
                    raise ValueError("Incomplete audit exists; use a new directory: " + str(output))
                path = source_file(args.data, source, args.cache)
                report = audit_file(path, source, output)
                print(json.dumps(report), flush=True)
                coverage(args.data)
        result = coverage(args.data)
    print(json.dumps({k: v for k, v in result.items() if k != "countries"}), flush=True)


if __name__ == "__main__":
    main()
