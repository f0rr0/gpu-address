"""Acquire a bounded, reproducible address pilot; never invent labels for real text."""

import argparse
import csv
import gzip
import hashlib
import io
import json
import random
import re
import tarfile
import time
import unicodedata
import urllib.parse
import urllib.request
import zipfile
import zlib
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .paths import ROOT
from .schema import FIELDS, SOURCE_FIELDS, Component

SENZING = "5113929832ac06619d18a4816f78a90fef8cc7a3"
WDC = "https://data.dws.informatik.uni-mannheim.de/structureddata/2024-12/quads/classspecific/LocalBusiness/"
SOURCES = {
    "osm-tagged": (
        "https://archive.org/download/libpostal-parser-training-data-20170304/formatted_addresses_tagged.random.tsv.gz",
        8 * 1024**2,
        "OSM-derived; retain ODbL attribution",
    ),
    "oa-tagged": (
        "https://archive.org/download/libpostal-parser-training-data-20170304/openaddresses_formatted_addresses_tagged.random.tsv.gz",
        8 * 1024**2,
        "OpenAddresses upstream licenses vary",
    ),
    "senzing-tagged": (
        "https://public-read-libpostal-data.s3.amazonaws.com/v1.2.0/training_data/senzing_formatted_random.tsv.tgz",
        4 * 1024**2,
        "Senzing/libpostal upstream data provenance applies",
    ),
    "wdc-real": (
        WDC + "part_0.gz",
        8 * 1024**2,
        "WDC extraction; retain original web page provenance",
    ),
    "senzing-benchmark": (
        f"https://raw.githubusercontent.com/Senzing/libpostal-data/{SENZING}/files/tests/v1.2.0/test_data.csv",
        None,
        "Senzing public benchmark; source provenance retained",
    ),
}


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def identity(text):
    return "".join(c for c in unicodedata.normalize("NFKC", text).casefold() if c.isalnum())


def fetch(item, directory):
    name, (url, limit, license_note) = item
    path = directory / (name + ".raw")
    meta = directory / (name + ".json")
    if path.exists() and meta.exists():
        result = json.loads(meta.read_text())
        if hashlib.sha256(path.read_bytes()).hexdigest() != result["sha256"]:
            raise ValueError(f"Cached source hash mismatch: {name}")
        return result
    headers = {"User-Agent": "address-parser-research/0.1"}
    if limit:
        headers["Range"] = f"bytes=0-{limit - 1}"
    for attempt in range(3):
        try:
            with urllib.request.urlopen(
                urllib.request.Request(url, headers=headers), timeout=60
            ) as response:
                payload = response.read(limit or 10 * 1024**2)
                result = dict(
                    name=name,
                    url=url,
                    bytes=len(payload),
                    http_status=response.status,
                    sha256=hashlib.sha256(payload).hexdigest(),
                    license_note=license_note,
                    sampling="compressed prefix; NOT a representative random sample"
                    if limit
                    else "complete bounded file",
                    retrieved_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                )
            temporary = path.with_suffix(".tmp")
            temporary.write_bytes(payload)
            temporary.replace(path)
            meta.write_text(json.dumps(result, indent=2))
            print(json.dumps(result), flush=True)
            return result
        except Exception:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def prefix_text(path, tar=False):
    raw = zlib.decompressobj(31).decompress(path.read_bytes())
    if tar:
        name = raw[:100].split(b"\0")[0]
        if not name.endswith(b".tsv"):
            raise ValueError(f"Unexpected first tar member: {name!r}")
        size = tarfile.TarInfo.frombuf(raw[:512], "utf-8", "strict").size
        raw = raw[512 : 512 + size]
    # A compressed prefix can end in the middle of a UTF-8 character or a row.
    return raw[: raw.rfind(b"\n") + 1].decode("utf-8", errors="strict")


def tagged(line):
    language, country, body = line.rstrip("\n").split("\t", 2)
    pieces = []
    for pair in body.split():
        token, label = pair.rsplit("/", 1)
        if label in ("SEP", "FSEP"):
            pieces.append((",", None))
        elif label in SOURCE_FIELDS and token:
            pieces.append((token, label))
        else:
            raise ValueError(f"Unknown label {label}")
    text = ""
    spans: list[Component] = []
    previous = None
    for token, label in pieces:
        if text:
            text += " "
        start = len(text)
        text += token
        if label:
            if previous == label:
                spans[-1]["end"] = len(text)
                spans[-1]["raw"] = text[spans[-1]["start"] :]
            else:
                spans.append(dict(label=label, start=start, end=len(text), raw=token))
        previous = label
    return dict(
        text=text,
        components=spans,
        country=country.lower(),
        language=language,
        label_provenance="existing-tagged",
        offset_basis="reconstructed-input",
        status=None,
    )


def group(row):
    fields = defaultdict(list)
    for component in row["components"]:
        fields[component["label"]].append(identity(component["raw"]))
    # Group streets within localities; country hints are never passed to the model.
    if fields["road"] and (fields["city"] or fields["postcode"]):
        return digest(
            "|".join(
                [
                    row["country"],
                    " ".join(fields["road"]),
                    " ".join(fields["city"] or fields["postcode"]),
                ]
            )
        )
    return digest(row["country"] + "|" + identity(row["text"]))


def validate(row):
    previous = 0
    for span in row["components"]:
        assert span["label"] in SOURCE_FIELDS or span["label"] in FIELDS
        assert previous <= span["start"] < span["end"] <= len(row["text"])
        assert row["text"][span["start"] : span["end"]] == span["raw"]
        previous = span["end"]


def variant(row, seed):
    rng = random.Random(seed)
    case = rng.choice(["original", "original", "lower", "upper"])
    layout = rng.choice(["source", "source", "spaces", "mixed"])
    omit = None
    parts = row["components"]
    if rng.random() < 0.2 and len(parts) > 2:
        omit = rng.randrange(len(parts))
        parts = [part for i, part in enumerate(parts) if i != omit]
    text, spans = "", []
    previous = None
    for part in parts:
        value = part["raw"]
        if case == "lower":
            value = value.lower()
        elif case == "upper":
            value = value.upper()
        if text:
            if layout == "source" and previous is not None:
                gap = row["text"][previous["end"] : part["start"]]
                # An omitted field must not be copied back as part of a gap.
                text += gap if not any(char.isalnum() for char in gap) else " "
            else:
                text += " " if layout == "spaces" else rng.choice([" ", " ", ", ", "\n"])
        start = len(text)
        text += value
        spans.append(dict(label=part["label"], start=start, end=len(text), raw=value))
        previous = part
    return dict(
        row,
        text=text,
        components=spans,
        id=row["id"] + "-independent-variant",
        label_provenance="controlled-augmentation",
        augmentation=dict(case=case, layout=layout, omitted_component=omit),
        base_id=row["id"],
    )


def compact_cjk(row):
    text, spans = "", []
    for part in row["components"]:
        value = re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", part["raw"])
        if text and not ("\u3400" <= text[-1] <= "\u9fff" and "\u3400" <= value[0] <= "\u9fff"):
            text += " "
        start = len(text)
        text += value
        spans.append(dict(label=part["label"], start=start, end=len(text), raw=value))
    return dict(
        row,
        text=text,
        components=spans,
        id=row["id"] + "-compact-cjk",
        label_provenance="controlled-augmentation",
        augmentation="compact-cjk",
        base_id=row["id"],
    )


def write_rows(path, rows):
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def web_rows(text):
    # Parse actual N-Quads syntax; page-scoped blank node IDs cannot be joined globally.
    from rdflib import Literal
    from rdflib.plugins.parsers.nquads import NQuadsParser

    class Sink:
        def __init__(self):
            self.items = []

        def get_context(self, context):
            self.context = str(context)
            return self

        def add(self, triple):
            self.items.append((self.context, triple))

    sink = Sink()
    parser = NQuadsParser()
    parser.sink = sink  # ty: ignore[invalid-assignment] -- rdflib accepts this minimal add() sink at runtime.
    nodes = defaultdict(dict)
    invalid = 0
    wanted = {"streetAddress", "addressLocality", "addressRegion", "postalCode", "addressCountry"}
    for line in text.splitlines():
        if not any("/" + field + ">" in line for field in wanted):
            continue
        parser.line = line
        try:
            parser.parseline()
        except Exception:
            invalid += 1
            continue
        for page, (subject, predicate, value) in sink.items:
            field = str(predicate).rsplit("/", 1)[-1]
            if isinstance(value, Literal) and field in wanted:
                nodes[(page, str(subject))][field] = str(value)
        sink.items.clear()
    result, seen = [], set()
    for (page, subject), fields in nodes.items():
        raw = fields.get("streetAddress", "").strip()
        if not raw or len(raw) > 512 or identity(raw) in seen:
            continue
        seen.add(identity(raw))
        result.append(
            dict(
                id="wdc-" + digest(page + "|" + subject),
                text=raw,
                source="wdc-real",
                source_url=page,
                source_subject=subject,
                domain=urllib.parse.urlparse(page).hostname,
                source_fields=fields,
                country=fields.get("addressCountry", ""),
                label_provenance="unlabeled-real",
                components=None,
                status=None,
                annotation_status="needs-review",
            )
        )
    return result, invalid


def review_queue(rows, limit=250):
    """Select a deterministic, raw-text-only natural review queue."""

    def present(row, field):
        return bool(str(row.get("source_fields", {}).get(field, "")).strip())

    def script(row):
        return "nonlatin" if any(ord(c) > 127 for c in row["text"]) else "latin"

    def family(row):
        text = row["text"]
        return "multiline" if "\n" in text else "delimited" if "," in text else "single-line"

    def key(row):
        fields = row.get("source_fields", {})
        complete = all(
            present(row, field) for field in ("addressLocality", "postalCode", "addressCountry")
        )
        return (
            row.get("domain") or "",
            str(fields.get("addressCountry", "")).casefold(),
            script(row),
            family(row),
            "complete" if complete else "street-only",
        )

    def natural_complete(row):
        # Metadata is evidence only when its value is present in the original text.
        text = identity(row["text"])
        fields = row.get("source_fields", {})
        values = [
            str(fields.get(field, "")).strip()
            for field in ("addressLocality", "postalCode", "addressCountry")
        ]
        return all(value and identity(value) in text for value in values)

    groups = defaultdict(list)
    for row in rows:
        if len(row["text"]) < 4 or not any(c.isalpha() for c in row["text"]):
            continue
        row = dict(row, review_natural_complete=natural_complete(row))
        groups[key(row) + ("complete" if row["review_natural_complete"] else "partial",)].append(
            row
        )
    for values in groups.values():
        values.sort(key=lambda row: digest(row["id"]))
    selected = []
    # Round-robin complete natural rows first, then partial rows as fallback.
    for wanted in ("complete", "partial"):
        eligible = {k: v for k, v in groups.items() if k[-1] == wanted}
        while len(selected) < limit and eligible:
            for group_key in sorted(tuple(eligible)):
                values = eligible[group_key]
                if values:
                    selected.append(values.pop(0))
                    if len(selected) == limit:
                        break
                if not values:
                    del eligible[group_key]
            if not any(eligible.values()):
                break
        if len(selected) == limit:
            break
    for row in selected:
        row["review_split"] = (
            "natural-complete" if row["review_natural_complete"] else "natural-partial"
        )
        row["review_stratum"] = "/".join(str(part) for part in key(row))
    return selected


def extras(directory):
    """Prepare fresh structured examples and rejection-review material separately."""
    raw = directory / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    street_fields = [
        "PRE_MODIFIER",
        "PRE_DIRECTIONAL",
        "PRE_TYPE",
        "STREET_NAME",
        "POST_TYPE",
        "POST_DIRECTIONAL",
        "POST_MODIFIER",
    ]
    fields = ["ADDRESSPOINTID", "HOUSE_NUMBER", "ZIPCODE"] + street_fields
    query = urllib.parse.urlencode(
        dict(
            where="1=1",
            outFields=",".join(fields),
            resultRecordCount=1000,
            orderByFields="ADDRESSPOINTID",
            returnGeometry="false",
            f="json",
        )
    )
    api = "https://services6.arcgis.com/yG5s3afENB5iO9fj/arcgis/rest/services/AddressPoint_view/FeatureServer/0/query?"
    sources = [
        fetch(
            (
                "nyc-structured",
                (api + query, None, "NYC AddressPoint upstream terms; OA descriptor c72d304"),
            ),
            raw,
        ),
        fetch(
            (
                "enron-contexts",
                (
                    "https://www.cs.cmu.edu/~einat/EnronRandom-Minorthird.zip",
                    None,
                    "CMU research corpus; original email provenance retained",
                ),
            ),
            raw,
        ),
    ]
    payload = json.loads((raw / "nyc-structured.raw").read_text())
    if "error" in payload:
        raise ValueError(payload["error"])
    generated = []
    for record in payload["features"]:
        source = record["attributes"]
        values = [
            ("house_number", str(source.get("HOUSE_NUMBER") or "").strip()),
            (
                "road",
                " ".join(str(source.get(field) or "").strip() for field in street_fields).strip(),
            ),
            ("postcode", str(source.get("ZIPCODE") or "").strip()),
        ]
        values = [(label, re.sub(r"\s+", " ", value)) for label, value in values if value]
        text, spans = "", []
        for label, value in values:
            if text:
                text += ", " if label == "postcode" else " "
            start = len(text)
            text += value
            spans.append(dict(label=label, start=start, end=len(text), raw=value))
        row = dict(
            id="nyc-" + str(source["ADDRESSPOINTID"]),
            text=text,
            components=spans,
            country="us",
            source="nyc-addresspoint",
            source_record=source,
            label_provenance="generated-from-fields",
            status=None,
            annotation_status="provider-fields; mapping-audit-pending",
            split="staging",
        )
        validate(row)
        generated.append(row)
    write_rows(directory / "structured-generated-staging.jsonl.gz", generated)
    contexts, seen = [], set()
    with zipfile.ZipFile(raw / "enron-contexts.raw") as archive:
        for entry in archive.namelist():
            if (
                entry.endswith("/")
                or "/enron" not in entry
                or entry.endswith((".labels", ".mixup"))
            ):
                continue
            text = archive.read(entry).decode("utf-8", errors="replace")
            for paragraph in re.split(r"\n\s*\n", text):
                paragraph = paragraph.strip()
                if not 40 <= len(paragraph) <= 300 or identity(paragraph) in seen:
                    continue
                if paragraph.startswith(("Message-ID:", "From:", "To:", "Date:", "Subject:")):
                    continue
                seen.add(identity(paragraph))
                contexts.append(
                    dict(
                        id="enron-" + digest(entry + paragraph),
                        text=paragraph,
                        source="enron-random",
                        source_record=entry,
                        components=None,
                        status=None,
                        label_provenance="unlabeled-real",
                        annotation_status="needs-address-presence-review",
                    )
                )
    random.Random(2026).shuffle(contexts)
    write_rows(directory / "rejection-review-candidates.jsonl.gz", contexts[:500])
    negatives = [
        "Your password reset link has expired.",
        "Add 3 items to your shopping cart.",
        "HTTP/1.1 404 Not Found",
        "subtotal: 49.99; tax: 4.50; total: 54.49",
        "Meeting postponed until Friday.",
        "const x = 42;",
        "Payment reference INV-2026-0042",
        "Please update your browser to continue.",
    ]
    write_rows(
        directory / "authored-negative-regressions.jsonl.gz",
        [
            dict(
                id=f"negative-{i}",
                text=text,
                components=[],
                status="not_address",
                label_provenance="authored-regression",
                source="experiment-authored",
                split="regression",
            )
            for i, text in enumerate(negatives)
        ],
    )
    report = dict(
        sources=sources,
        structured_generated=len(generated),
        real_contexts_for_review=min(len(contexts), 500),
        authored_negatives=len(negatives),
        used_in_training=False,
        reason="Additional staging sources require mapping/label review and dedup before mixing with training",
    )
    (directory / "extras-manifest.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=ROOT / "data")
    ap.add_argument("--max-per-source", type=int, default=35000)
    ap.add_argument("--extras-only", action="store_true")
    args = ap.parse_args(argv)
    args.data.mkdir(parents=True, exist_ok=True)
    if args.extras_only:
        extras(args.data)
        return
    raw = args.data / "raw"
    raw.mkdir(exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as executor:
        sources = list(executor.map(lambda item: fetch(item, raw), SOURCES.items()))
    benchmark = []
    excluded_ids, excluded_groups = set(), set()
    for record in csv.DictReader(io.StringIO((raw / "senzing-benchmark.raw").read_text())):
        components = [dict(label=k, raw=record[k]) for k in SOURCE_FIELDS if record.get(k)]
        row = dict(
            id="senzing-test-" + record["record_id"],
            text=record["full_address"],
            components=components,
            country=record["country_code"].lower(),
            label_provenance="public-benchmark",
            source=record["source"],
            status=None,
            offset_basis=None,
        )
        benchmark.append(row)
        excluded_ids.add(identity(row["text"]))
        excluded_groups.add(group(row))
    write_rows(args.data / "public-benchmark.jsonl.gz", benchmark)
    pools = defaultdict(list)
    seen, stats = set(), Counter()
    for name in ["osm-tagged", "oa-tagged", "senzing-tagged"]:
        lines = prefix_text(raw / (name + ".raw"), tar=name == "senzing-tagged").splitlines()
        # Shuffle within the retrieved prefix; this does not make the source prefix representative.
        random.Random(2026).shuffle(lines)
        kept = 0
        for index, line in enumerate(lines):
            if kept >= args.max_per_source:
                break
            try:
                row = tagged(line)
                validate(row)
            except (ValueError, AssertionError):
                stats[name + ":invalid"] += 1
                continue
            if not row["components"] or len(row["text"]) > 512:
                stats[name + ":empty-or-long"] += 1
                continue
            key = identity(row["text"])
            grouping = group(row)
            if key in excluded_ids or grouping in excluded_groups:
                stats[name + ":benchmark-overlap"] += 1
                continue
            if key in seen:
                stats[name + ":duplicate"] += 1
                continue
            seen.add(key)
            split = "dev" if int(grouping[:8], 16) % 10 == 0 else "train"
            row.update(
                id=name + "-" + digest(line),
                source=name,
                group_id=grouping,
                split=split,
                source_line_hash=digest(line),
            )
            pools[split].append(row)
            kept += 1
        stats[name + ":kept"] = kept
    # Variants inherit source group and split; no new split after augmentation.
    prepared = {}
    for split in ["train", "dev"]:
        originals = pools[split]
        variants = [variant(row, row["id"]) for row in originals]
        variants += [
            compact_cjk(row)
            for row in originals
            if row["country"] in ("cn", "jp", "tw")
            and re.search(r"[\u3400-\u9fff]\s+[\u3400-\u9fff]", row["text"])
        ]
        for row in variants:
            validate(row)
        prepared[split] = originals + variants
        stats[split + ":originals"] = len(originals)
        stats[split + ":variants"] = len(variants)
    dev_identities = {identity(row["text"]) for row in prepared["dev"]}
    before = len(prepared["train"])
    prepared["train"] = [
        row
        for row in prepared["train"]
        if identity(row["text"]) not in dev_identities and identity(row["text"]) not in excluded_ids
    ]
    stats["train:post-augmentation-overlap-removed"] = before - len(prepared["train"])
    for split, rows in prepared.items():
        write_rows(args.data / (split + ".jsonl.gz"), rows)
        stats[split + ":written"] = len(rows)
    real, invalid = web_rows(prefix_text(raw / "wdc-real.raw"))
    write_rows(args.data / "unlabeled-real.jsonl.gz", real)
    stats["unlabeled-real"] = len(real)
    stats["wdc-invalid-lines"] = invalid
    # A queue is not gold until humans label it; never substitute teacher predictions.
    review = review_queue(real)
    write_rows(args.data / "annotation-queue.jsonl.gz", review)
    stats["annotation-queue"] = len(review)
    stats["annotation-natural-complete"] = sum(
        row["review_split"] == "natural-complete" for row in review
    )
    stats["annotation-natural-partial"] = sum(
        row["review_split"] == "natural-partial" for row in review
    )
    manifest = dict(
        version=1,
        seed=2026,
        sources=sources,
        counts=dict(stats),
        countries={
            split: dict(Counter(row["country"] for row in rows)) for split, rows in pools.items()
        },
        fields=dict(Counter(s["label"] for row in pools["train"] for s in row["components"])),
        limitations=[
            "Bounded archive prefixes, not global representative samples",
            "Original source IDs unavailable in tagged corpora; conservative street groups and normalized dedup only",
            "No independent human gold or real-negative labels yet",
            "No learned abstention/status claim; field parsing only",
            "Generated variants are not real messy examples",
        ],
    )
    (args.data / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == "__main__":
    main()
