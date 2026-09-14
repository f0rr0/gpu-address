"""Acquire bounded additional sources, audit labels, and build an isolated corpus."""

import argparse
import csv
import gzip
import hashlib
import json
import random
import re
import shutil
import time
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .paths import ROOT, SOURCE
from .prepare import (
    compact_cjk,
    digest,
    group,
    identity,
    prefix_text,
    tagged,
    validate,
    variant,
    write_rows,
)

HF_REV = "cb61e5e49db87f8c3586b5494149f612460f8992"
CN_REV = "54cf6bde941a152cc096f54294254fc4ee288fa7"
GNAF_REV = "fe77dbd9d7ab802f074d5286a4b016a4813ed8a4"
COUNTRIES = [
    "tw",
    "eg",
    "li",
    "in",
    "kr",
    "at",
    "za",
    "sk",
    "sg",
    "kw",
    "tt",
    "ar",
    "gt",
    "ca",
    "dk",
]


def sources():
    result = {}
    for name in [
        "formatted_addresses_tagged",
        "formatted_places_tagged",
        "formatted_ways_tagged",
        "geoplanet_formatted_addresses_tagged",
        "openaddresses_formatted_addresses_tagged",
        "senzing_formatted_random",
    ]:
        result["senzing-" + name] = (
            f"https://public-read-libpostal-data.s3.amazonaws.com/v1.2.0/training_data/{name}.tsv.tgz",
            4 * 1024**2,
            True,
        )
    for country in COUNTRIES:
        result["worldwide-" + country] = (
            f"https://huggingface.co/datasets/deepparse/worldwide-addresses/resolve/{HF_REV}/{country}/chunk-0.parquet",
            256 * 1024**2,
            False,
        )
    for name in ["train.txt", "dev.txt", "test.txt", "labels.txt", "anno/anno-en.md"]:
        result["chinese-" + name.replace("/", "-")] = (
            f"https://raw.githubusercontent.com/leodotnet/neural-chinese-address-parsing/{CN_REV}/data/{name}",
            4 * 1024**2,
            False,
        )
    for department in ["75", "59", "974"]:
        result["ban-" + department] = (
            f"https://adresse.data.gouv.fr/data/ban/adresses/latest/csv/adresses-{department}.csv.gz",
            64 * 1024**2,
            False,
        )
    # Published G-NAF conversion, explicitly dated 2022; not the current official release.
    result["gnaf-2022-shard0"] = (
        f"https://huggingface.co/datasets/dylanhogg/gnaf-2022/resolve/{GNAF_REV}/data/train-00000-of-00010.parquet",
        256 * 1024**2,
        False,
    )
    result["gnaf-2022-readme"] = (
        f"https://huggingface.co/datasets/dylanhogg/gnaf-2022/resolve/{GNAF_REV}/README.md",
        1024**2,
        False,
    )
    result["older-deepparse"] = (
        "https://graal.ift.ulaval.ca/public/deepparse/dataset/data.zip",
        64 * 1024**2,
        False,
    )
    result["worldwide-readme"] = (
        f"https://huggingface.co/datasets/deepparse/worldwide-addresses/resolve/{HF_REV}/README.md",
        1024**2,
        False,
    )
    return result


HF_LABELS = dict(
    StreetNumber="house_number",
    StreetName="road",
    Unit="unit",
    Suburb="suburb",
    District="city_district",
    PostalCode="postcode",
    Municipality="city",
    Province="state",
    County="state_district",
    Country="country",
)


def hf_row(record, country):
    words = record["Address"].split()
    tags = record["Tags"]
    if len(words) != len(tags) or not words:
        raise ValueError("token-label-length")
    if any(tag not in HF_LABELS for tag in tags):
        raise ValueError("unknown-tag")
    row = tagged(
        record.get("Language", "")
        + "\t"
        + country
        + "\t"
        + " ".join(word + "/" + HF_LABELS[tag] for word, tag in zip(words, tags))
    )
    row["label_provenance"] = "mapped-existing-tags"
    return row


def render(values, country, record_id):
    text, spans = "", []
    for label, value in values:
        if not value:
            continue
        if text:
            text += " "
        start = len(text)
        text += value
        spans.append(dict(label=label, start=start, end=len(text), raw=value))
    return dict(
        text=text,
        components=spans,
        country=country,
        language="",
        source_record_id=record_id,
        label_provenance="generated-from-fields",
        offset_basis="rendered-input",
        status=None,
    )


def ban_row(record, department):
    if record.get("certification_commune") != "1":
        raise ValueError("not-municipality-certified")
    number, road, postcode, city = (
        record[k].strip() for k in ["numero", "nom_voie", "code_postal", "libelle_acheminement"]
    )
    if (
        not number.isdigit()
        or int(number) in (0, 9999)
        or not road
        or not city
        or not re.fullmatch(r"\d{5}", postcode)
    ):
        raise ValueError("missing-or-invalid-core-fields")
    row = render(
        [
            ("house_number", number + record.get("rep", "").strip()),
            ("road", road),
            ("postcode", postcode),
            ("city", city),
        ],
        "re" if department == "974" else "fr",
        record["id"],
    )
    row["source_fields"] = {
        k: record[k]
        for k in [
            "numero",
            "rep",
            "nom_voie",
            "code_postal",
            "libelle_acheminement",
            "nom_commune",
            "code_insee",
            "certification_commune",
        ]
    }
    return row


def numeric(value):
    if value is None or value == "":
        return ""
    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError("noninteger-number")
        return str(int(value))
    return str(value)


def gnaf_row(record):
    if record["confidence"] < 0 or record["alias_principal"] != "P":
        raise ValueError("retired-or-alias")

    def number(prefix):
        value = numeric(record[prefix])
        return (
            (
                numeric(record.get(prefix + "_prefix"))
                + value
                + numeric(record.get(prefix + "_suffix"))
            )
            if value
            else ""
        )

    first, last = number("number_first"), number("number_last")
    if not first or not record["street_name"] or record["postcode"] is None:
        raise ValueError("missing-street-number-road-or-postcode")
    postcode = numeric(record["postcode"]).zfill(4)
    if not re.fullmatch(r"\d{4}", postcode):
        raise ValueError("invalid-postcode")
    values = [
        ("house", record["building_name"]),
        ("unit", " ".join(filter(None, [record["flat_type"], number("flat_number")]))),
        ("level", " ".join(filter(None, [record["level_type"], number("level_number")]))),
        ("house_number", first + ("-" + last if last else "")),
        (
            "road",
            " ".join(
                filter(
                    None,
                    [
                        record["street_name"],
                        record["street_type_code"],
                        record["street_suffix_type"],
                    ],
                )
            ),
        ),
        ("state", record["state_abbreviation"]),
        ("postcode", postcode),
    ]
    row = render(values, "au", record["address_detail_pid"])
    # Postal localities can map to city or suburb in libpostal. Do not manufacture
    # that distinction: deliberately generate partial inputs without the locality.
    row.update(
        omitted_source_fields=["locality_name", "lot_number"],
        source_fields=record,
        source_entity_group=record["street_locality_pid"],
    )
    return row


def parquet_sample(path, count=12000):
    import pyarrow.parquet as pq

    source = pq.ParquetFile(path)
    positions = sorted(
        random.Random(2026).sample(
            range(source.metadata.num_rows), min(count, source.metadata.num_rows)
        )
    )
    cursor, offset = 0, 0
    for batch in source.iter_batches(batch_size=32768):
        indices = []
        while cursor < len(positions) and positions[cursor] < offset + len(batch):
            indices.append(positions[cursor] - offset)
            cursor += 1
        if indices:
            yield from batch.take(indices).to_pylist()
        offset += len(batch)


def csv_sample(path, count=12000):
    rng, rows, seen = random.Random(2026), [], 0
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for seen, row in enumerate(csv.DictReader(stream, delimiter=";"), 1):
            if len(rows) < count:
                rows.append(row)
            else:
                i = rng.randrange(seen)
                if i < count:
                    rows[i] = row
    return rows


def audit(directory):
    from .tokenizer import components, encode

    raw = directory / "raw"
    accepted, quarantine, reports = [], [], {}
    acquisitions = json.loads((directory / "acquisition.json").read_text())
    for entry in acquisitions:
        name = entry["name"]
        if entry["status"] != "acquired":
            reports[name] = dict(status="unavailable", error=entry.get("error"))
            continue
        path = raw / (name + ".raw")
        counts, labels, countries, examples = Counter(), Counter(), Counter(), []
        if name.startswith("chinese-"):
            if name not in ["chinese-train.txt", "chinese-dev.txt", "chinese-test.txt"]:
                continue
            for block in path.read_text().strip().split("\n\n"):
                pairs = [line.rsplit(None, 1) for line in block.splitlines()]
                counts["rows"] += 1
                previous = None
                for word, tag in pairs:
                    labels[tag[2:]] += 1
                    if tag.startswith("I-") and previous not in ("B-" + tag[2:], tag):
                        counts["invalid-BIO-transitions"] += 1
                    previous = tag
                if len(examples) < 8:
                    examples.append(
                        dict(text="".join(p[0] for p in pairs), tags=[p[1] for p in pairs])
                    )
            reports[name] = dict(
                counts=counts,
                labels=labels,
                examples=examples,
                status="quarantined",
                reason="Schema has district/town/community and building/room distinctions not safely mapped; dataset reuse terms not established. Preserve published splits.",
            )
            continue
        if name.startswith("senzing-"):
            lines = prefix_text(path, True).splitlines()
            records = random.Random(2026).sample(lines, min(25000, len(lines)))
            convert = tagged
        elif name.startswith("worldwide-") and name != "worldwide-readme":
            records = parquet_sample(path)

            def convert(record):
                return hf_row(record, name.rsplit("-", 1)[1])
        elif name.startswith("ban-"):
            records = csv_sample(path)

            def convert(record):
                return ban_row(record, name.rsplit("-", 1)[1])
        elif name == "gnaf-2022-shard0":
            records, convert = parquet_sample(path), gnaf_row
        else:
            continue
        local = []
        for i, record in enumerate(records):
            counts["examined"] += 1
            try:
                row = convert(record)
                validate(row)
                item = encode(row)
                if item is None:
                    raise ValueError("input-limits-or-empty")
                if components(item[1], item[2], row["text"]) != row["components"]:
                    raise ValueError("tokenizer-cannot-represent-spans")
            except (ValueError, AssertionError, KeyError) as error:
                counts["rejected:" + str(error)] += 1
                quarantine.append(
                    dict(
                        source=name, source_sample_index=i, reason=str(error), source_record=record
                    )
                )
                continue
            row.update(
                source=name,
                id=name + "-" + digest(json.dumps(record, ensure_ascii=False, sort_keys=True)),
                source_sample_index=i,
                source_sha256=entry["sha256"],
            )
            row["group_id"] = group(row)
            counts["structurally-valid"] += 1
            labels.update(c["label"] for c in row["components"])
            countries[row["country"]] += 1
            counts["with-road"] += any(c["label"] == "road" for c in row["components"])
            counts["with-house-number"] += any(
                c["label"] == "house_number" for c in row["components"]
            )
            if len(examples) < 8:
                examples.append(row)
            local.append(row)
        accepted.extend(local)
        reports[name] = dict(
            status="structural-audit-complete",
            counts=counts,
            fields=labels,
            countries=countries,
            examples=examples,
            semantic_accuracy="not established by structural checks",
        )
        print(json.dumps(dict(source=name, counts=counts, countries=countries)), flush=True)
    write_rows(directory / "candidate-originals.jsonl.gz", accepted)
    write_rows(directory / "quarantine.jsonl.gz", quarantine)
    (directory / "quality-audit.json").write_text(json.dumps(reports, indent=2, ensure_ascii=False))


def label_signature(row):
    fields = defaultdict(str)
    for span in row["components"]:
        fields[span["label"]] += identity(span["raw"])
    return tuple(sorted(fields.items()))


def street_keys(row):
    fields = defaultdict(str)
    for span in row["components"]:
        fields[span["label"]] += identity(span["raw"])
    return {
        digest(row["country"] + "|" + fields["road"] + "|" + key + "|" + fields[key])
        for key in ["city", "postcode"]
        if fields["road"] and fields[key]
    }


def quality_reason(row):
    if row["country"] == "sg" and "pasirgudang" in identity(row["text"]):
        return "known-geographic-contamination:Pasir-Gudang-is-in-Johor"
    if any(
        c["label"] == "road"
        and identity(c["raw"]) in {"ninguno", "sinnombre", "unnamed", "unknown"}
        for c in row["components"]
    ):
        return "placeholder-road"
    return None


def build(directory):
    from .tokenizer import components, encode

    base = ROOT / "data/layout-independent"

    def read(path):
        with gzip.open(path, "rt") as stream:
            return list(map(json.loads, stream))

    if (directory / "train.jsonl.gz").exists():
        raise ValueError("Expanded corpus already exists; use a new directory/version")
    train, dev = read(base / "train.jsonl.gz"), read(base / "dev.jsonl.gz")
    public = read(base / "public-benchmark.jsonl.gz")
    old_ids = {identity(r["text"]): label_signature(r) for r in train}
    old_groups = {r["group_id"] for r in train}
    old_streets = set().union(*(street_keys(r) for r in train))
    protected_ids = {identity(r["text"]) for r in dev + public}
    protected_groups = {group(r) for r in dev + public}
    protected_streets = set().union(*(street_keys(r) for r in dev + public))
    candidates = read(directory / "candidate-originals.jsonl.gz")
    signatures, conflicts = {}, set()
    for row in candidates:
        key, signature = identity(row["text"]), label_signature(row)
        if key in signatures and signatures[key] != signature:
            conflicts.add(key)
        signatures[key] = signature
    counters, per_source, reasons = Counter(), defaultdict(Counter), []
    new_train, heldout, seen = [], [], set()
    quotas, groups = Counter(), Counter()
    # Hash order mixes the entire audited sample. Caps prevent place fragments,
    # archive prefixes, and many variants of one street from dominating additions.
    for row in sorted(candidates, key=lambda r: digest(r["id"])):
        source, key = row["source"], identity(row["text"])
        reason = quality_reason(row)
        if not reason and key in conflicts:
            reason = "conflicting-candidate-labels"
        if not reason and key in old_ids:
            reason = (
                "existing-training-duplicate"
                if old_ids[key] == label_signature(row)
                else "conflict-with-existing-training"
            )
        if not reason and (
            key in protected_ids
            or row["group_id"] in protected_groups
            or street_keys(row) & protected_streets
        ):
            reason = "protected-evaluation-overlap"
        if not reason and key in seen:
            reason = "new-source-duplicate"
        if reason:
            per_source[source][reason] += 1
            if reason not in [
                "existing-training-duplicate",
                "new-source-duplicate",
                "protected-evaluation-overlap",
            ]:
                reasons.append(dict(row=row, reason=reason))
            continue
        seen.add(key)
        full = any(c["label"] == "house_number" for c in row["components"]) and any(
            c["label"] == "road" for c in row["components"]
        )
        category = "number-and-road" if full else "partial"
        quota = (source, row["country"], category)
        cap = 5000 if full else 1000
        if quotas[quota] >= cap or groups[row["group_id"]] >= 8:
            per_source[source]["mixture-or-street-cap"] += 1
            continue
        quotas[quota] += 1
        groups[row["group_id"]] += 1
        row["quality_status"] = "structural-and-targeted-audit; semantic-accuracy-unmeasured"
        row["split"] = (
            "train"
            if row["group_id"] in old_groups
            or street_keys(row) & old_streets
            or int(row["group_id"][:8], 16) % 10
            else "source-dev"
        )
        (new_train if row["split"] == "train" else heldout).append(row)
    # Protect supplementary holdout through both locality and postcode street keys.
    heldout_keys = set().union(*(street_keys(r) for r in heldout)) if heldout else set()
    heldout_groups = {r["group_id"] for r in heldout}
    heldout_ids = {identity(r["text"]) for r in heldout}
    selected = []
    for row in new_train:
        if row["group_id"] in heldout_groups or street_keys(row) & heldout_keys:
            per_source[row["source"]]["supplementary-holdout-overlap"] += 1
            continue
        selected.append(row)
        per_source[row["source"]]["added-originals"] += 1
    additions = []
    for row in selected:
        variants = [row, variant(row, row["id"])]
        if row["country"] in ["cn", "tw", "jp"] and re.search(
            r"[\u3400-\u9fff]\s+[\u3400-\u9fff]", row["text"]
        ):
            variants.append(compact_cjk(row))
        for changed in variants:
            key = identity(changed["text"])
            if key in protected_ids or key in heldout_ids:
                counters["variant-protected-overlap"] += 1
                continue
            validate(changed)
            item = encode(changed)
            if (
                item is None
                or components(item[1], item[2], changed["text"]) != changed["components"]
            ):
                counters["variant-not-representable"] += 1
                continue
            additions.append(changed)
    variant_signatures = dict(old_ids)
    variant_conflicts = set()
    for row in additions:
        key, signature = identity(row["text"]), label_signature(row)
        if key in variant_signatures and variant_signatures[key] != signature:
            variant_conflicts.add(key)
        variant_signatures[key] = signature
    counters["variant-conflicting-inputs"] = len(variant_conflicts)
    before = len(additions)
    additions = [r for r in additions if identity(r["text"]) not in variant_conflicts]
    counters["variant-conflict-rows-removed"] = before - len(additions)
    retained_originals = [
        r for r in additions if r["label_provenance"] != "controlled-augmentation"
    ]
    for source, values in per_source.items():
        values["selected-originals-before-variant-filters"] = values.pop("added-originals", 0)
        values["added-originals"] = sum(r["source"] == source for r in retained_originals)
    train.extend(additions)
    write_rows(directory / "train.jsonl.gz", train)
    # Fixed development and public datasets remain byte-for-byte unchanged.
    for name in [
        "dev.jsonl.gz",
        "public-benchmark.jsonl.gz",
        "unlabeled-real.jsonl.gz",
        "annotation-queue.jsonl.gz",
    ]:
        shutil.copy2(base / name, directory / name)
    write_rows(directory / "source-dev.jsonl.gz", heldout)
    write_rows(directory / "quality-exclusions.jsonl.gz", reasons)
    report = dict(
        version=2,
        parent=str(base),
        parent_manifest_sha256=hashlib.sha256((base / "manifest.json").read_bytes()).hexdigest(),
        sources=json.loads((directory / "acquisition.json").read_text()),
        code_sha256={
            name: hashlib.sha256((SOURCE / name).read_bytes()).hexdigest()
            for name in ["prepare.py", "expand.py"]
        },
        counts=dict(
            train=len(train),
            original_base_train=len(train) - len(additions),
            added_originals=len(retained_originals),
            added_with_variants=len(additions),
            dev=len(dev),
            source_dev=len(heldout),
            candidate_rows=len(candidates),
            conflicting_normalized_inputs=len(conflicts),
            **counters,
        ),
        source_decisions=per_source,
        added_original_countries=Counter(r["country"] for r in retained_originals),
        limitations=[
            "Bounded additional samples, not all worldwide data",
            "Structural checks do not establish semantic label accuracy",
            "No independently human-annotated new gold",
            "Older Deepparse archive unavailable; Chinese schema quarantined",
            "GNAF is a 2022 converted shard; rendered partial addresses omit ambiguous locality mapping",
            "Original physical-entity IDs unavailable in tagged datasets; street/string exclusions are conservative but incomplete",
        ],
    )
    (directory / "manifest.json").write_text(json.dumps(report, indent=2))
    print(
        json.dumps(
            {k: v for k, v in report.items() if k not in ["sources", "source_decisions"]}, indent=2
        ),
        flush=True,
    )


def acquire(item, folder):
    name, (url, limit, prefix) = item
    path, meta = folder / (name + ".raw"), folder / (name + ".json")
    if path.exists() and meta.exists():
        record = json.loads(meta.read_text())
        if (
            record.get("url") != url
            or hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]
        ):
            raise ValueError("Cached source changed: " + name)
        return record
    headers = {"User-Agent": "address-parser-research/0.2"}
    if prefix:
        headers["Range"] = f"bytes=0-{limit - 1}"
    record = dict(
        name=name,
        url=url,
        retrieved_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        sampling="compressed prefix, not representative" if prefix else "complete named file/shard",
    )
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, headers=headers), timeout=30
        ) as response:
            payload = response.read(limit if prefix else limit + 1)
            if not prefix and len(payload) > limit:
                raise ValueError(f"File exceeds acquisition bound {limit}")
            record.update(
                http_status=response.status,
                bytes=len(payload),
                sha256=hashlib.sha256(payload).hexdigest(),
                etag=response.headers.get("ETag"),
                last_modified=response.headers.get("Last-Modified"),
            )
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(payload)
        temporary.replace(path)
        record["status"] = "acquired"
    except Exception as error:
        record.update(status="unavailable", error=str(error))
    meta.write_text(json.dumps(record, indent=2))
    print(json.dumps(record), flush=True)
    return record


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=ROOT / "data/multisource")
    ap.add_argument("--audit-only", action="store_true")
    ap.add_argument("--build-only", action="store_true")
    args = ap.parse_args(argv)
    raw = args.data / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    if args.build_only:
        build(args.data)
        return
    if args.audit_only:
        audit(args.data)
        return
    with ThreadPoolExecutor(max_workers=5) as executor:
        records = list(executor.map(lambda item: acquire(item, raw), sources().items()))
    (args.data / "acquisition.json").write_text(json.dumps(records, indent=2))


if __name__ == "__main__":
    main()
