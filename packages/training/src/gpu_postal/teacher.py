"""Frozen libpostal pseudo-labels and public-benchmark baseline; no implied gold."""

import argparse
import ctypes as C
import gzip
import hashlib
import json
import re
import time
import unicodedata
from collections import Counter
from pathlib import Path

from .paths import ROOT
from .prepare import validate, write_rows
from .schema import SOURCE_FIELDS as FIELDS


class Options(C.Structure):
    _fields_ = [("language", C.c_char_p), ("country", C.c_char_p)]


class Response(C.Structure):
    _fields_ = [
        ("num_components", C.c_size_t),
        ("components", C.POINTER(C.c_char_p)),
        ("labels", C.POINTER(C.c_char_p)),
    ]


def canonical(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def field_map(parts):
    # Public CSV provides one column per label, so this benchmark is field-content
    # agreement, NOT exact ordered-span accuracy. Do not compare the two metrics.
    result = {}
    for part in parts:
        field, value = part["label"], canonical(part["raw"])
        result[field] = (result.get(field, "") + " " + value).strip()
    return result


def align(text, parts):
    spans, cursor = [], 0
    for part in parts:
        pattern = r"\s+".join(re.escape(word) for word in part["raw"].split())
        if not pattern or part["label"] not in FIELDS:
            return None
        matches = list(re.finditer(pattern, text[cursor:], re.IGNORECASE))
        if len(matches) != 1:
            return None
        start, end = cursor + matches[0].start(), cursor + matches[0].end()
        spans.append(dict(label=part["label"], start=start, end=end, raw=text[start:end]))
        cursor = end
    # Unaligned meaningful text makes a pseudo-labeled sequence incomplete.
    remainder = list(text)
    for span in spans:
        remainder[span["start"] : span["end"]] = " " * (span["end"] - span["start"])
    if any(char.isalnum() for char in remainder):
        return None
    return spans


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--library", type=Path, required=True)
    ap.add_argument("--resources", type=Path, required=True)
    ap.add_argument("--data", type=Path, default=ROOT / "data/expanded")
    args = ap.parse_args(argv)
    library = C.CDLL(str(args.library))
    for fn in [
        "libpostal_setup_datadir",
        "libpostal_setup_parser_datadir",
        "libpostal_setup_language_classifier_datadir",
    ]:
        method = getattr(library, fn)
        method.argtypes = [C.c_char_p]
        method.restype = C.c_bool
        if not method(str(args.resources).encode()):
            raise RuntimeError(f"{fn} failed")
    library.libpostal_get_address_parser_default_options.restype = Options
    library.libpostal_parse_address.argtypes = [C.c_char_p, Options]
    library.libpostal_parse_address.restype = C.POINTER(Response)
    library.libpostal_address_parser_response_destroy.argtypes = [C.POINTER(Response)]
    options = library.libpostal_get_address_parser_default_options()

    def parse(text):
        response = library.libpostal_parse_address(text.encode(), options)
        if not response:
            raise RuntimeError("libpostal returned null")
        try:
            return [
                dict(
                    label=response.contents.labels[i].decode(),
                    raw=response.contents.components[i].decode(),
                )
                for i in range(response.contents.num_components)
            ]
        finally:
            library.libpostal_address_parser_response_destroy(response)

    assert field_map(parse("123 Main Street, Springfield, IL 62704"))["house_number"] == "123"
    provenance = dict(
        library_sha256=hashlib.sha256(args.library.read_bytes()).hexdigest(),
        code_revision="25099c506612b34b23b1bfe286ca6321fcf06f35",
        resources=[json.loads(p.read_text()) for p in sorted(args.resources.glob("*.tar.gz.json"))],
    )
    rows = []
    with gzip.open(args.data / "unlabeled-real.jsonl.gz", "rt") as source:
        for line in source:
            row = json.loads(line)
            parts = parse(row["text"])
            spans = align(row["text"], parts)
            row.update(
                teacher_components=parts,
                components=spans,
                status=None,
                label_provenance="teacher-labeled-real",
                annotation_status="unverified-teacher",
                alignment_status="exact-raw-alignment"
                if spans is not None
                else "needs-alignment-review",
            )
            if spans is not None:
                validate(row)
            rows.append(row)
    write_rows(args.data / "teacher-labeled-real.jsonl.gz", rows)
    # Keep pseudo-labels separate from clean supervision during the first campaign.
    stats = dict(
        rows=len(rows),
        aligned=sum(row["components"] is not None for row in rows),
        used_in_training=False,
        provenance=provenance,
    )
    (args.data / "teacher-labeling.json").write_text(json.dumps(stats, indent=2))
    counts, countries, predictions = Counter(), {}, []
    started = time.monotonic()
    with gzip.open(args.data / "public-benchmark.jsonl.gz", "rt") as source:
        for line in source:
            row = json.loads(line)
            predicted = parse(row["text"])
            expected = row["components"]
            exact = field_map(predicted) == field_map(expected)
            counts["rows"] += 1
            counts["exact_field_map"] += exact
            countries.setdefault(row["country"], Counter())
            countries[row["country"]]["rows"] += 1
            countries[row["country"]]["exact"] += exact
            predictions.append(dict(id=row["id"], teacher_components=predicted, exact=exact))
    write_rows(args.data / "baseline-predictions.jsonl.gz", predictions)
    report = dict(
        **counts,
        accuracy=counts["exact_field_map"] / counts["rows"],
        elapsed_s=time.monotonic() - started,
        countries=countries,
        metric="casefold/NFKC/whitespace-normalized field-map exact agreement; not spans",
        provenance=provenance,
    )
    (args.data / "baseline.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(stats), flush=True)
    print(
        json.dumps({k: v for k, v in report.items() if k not in ["countries", "provenance"]}),
        flush=True,
    )
    library.libpostal_teardown_parser()
    library.libpostal_teardown_language_classifier()
    library.libpostal_teardown()


if __name__ == "__main__":
    main()
