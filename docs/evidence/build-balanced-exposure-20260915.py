"""Materialize a fixed-budget exposure mix; never cap or overwrite the source corpus.

Square-root country/type weights are an experiment, not a population estimate.
Reference weights stay fixed when new sources arrive, so source volume cannot buy
more country exposure. Outputs use the existing training loader unchanged.
"""

import argparse
import gzip
import json
import math
import random
import runpy
import shutil
import sqlite3
import tempfile
from array import array
from collections import Counter, defaultdict
from pathlib import Path

from gpu_postal.consolidate import rows
from gpu_postal.corpus import address_type
from gpu_postal.expand import file_sha256, street_keys
from gpu_postal.prepare import digest, identity, validate
from gpu_postal.tokenizer import components, encode


def quotas(counts, budget):
    if budget <= 0 or not counts or any(n <= 0 for n in counts.values()):
        raise ValueError("Positive budget and nonempty positive reference counts required")
    weights = {key: math.sqrt(n) for key, n in counts.items()}
    total = sum(weights.values())
    raw = {key: budget * weight / total for key, weight in weights.items()}
    result = {key: math.floor(value) for key, value in raw.items()}
    order = sorted(raw, key=lambda key: (-(raw[key] - result[key]), key))
    for key in order[: budget - sum(result.values())]:
        result[key] += 1
    return result


def key(row):
    return (row.get("country") or "unknown").lower() + "/" + address_type(row)


def selfcheck():
    assert quotas({"a": 1, "b": 9}, 12) == {"a": 3, "b": 9}
    assert sum(quotas({"a": 1, "b": 1, "c": 1}, 10).values()) == 10
    assert quotas({"a": 1, "b": 1}, 1) == {"a": 1, "b": 0}
    for counts, budget in [({}, 10), ({"a": 0}, 10), ({"a": 1}, 0)]:
        try:
            quotas(counts, budget)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid allocation accepted")
    print("Fixed-budget allocation selfcheck passed")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", type=Path)
    ap.add_argument("--supplement", type=Path, nargs="*", default=[])
    ap.add_argument("--protect-queue", type=Path, nargs="*", default=[])
    ap.add_argument("--output", type=Path)
    ap.add_argument("--rows", type=int, default=4_343_094)
    ap.add_argument("--seed", type=int, default=20260915)
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args()
    if args.selfcheck:
        return selfcheck()
    if not args.base or not args.output:
        ap.error("--base and --output required")
    coverage = json.loads((args.base / "coverage.json").read_text())
    reference = {
        country + "/" + kind: n
        for country, entry in coverage.items()
        for kind, n in entry.get("address_types", {}).items()
        if n
    }
    allocation = quotas(reference, args.rows)
    helper = runpy.run_path(str(Path(__file__).with_name("assemble-data-version-20260915.py")))
    protected = helper["PROTECTED"]
    protected_text, protected_streets, protected_model = set(), set(), set()
    for path in protected:
        for row in rows(path):
            row = dict(row, country=(row.get("country") or "").lower())
            protected_text.add(identity(row["text"]))
            protected_streets.update(street_keys(row))
            item = encode(row, labeled=False)
            if item is not None:
                protected_model.add(digest(json.dumps(item[0])))
    for path in args.protect_queue:
        queue = json.loads(path.read_text())
        queued_rows = queue.get("candidates", queue.get("rows"))
        if not isinstance(queued_rows, list):
            raise ValueError("Protection queue must contain candidates or rows")
        for row in queued_rows:
            protected_text.add(identity(row["text"]))
            item = encode(row, labeled=False)
            if item is not None:
                protected_model.add(digest(json.dumps(item[0])))
    args.output.mkdir(parents=True, exist_ok=False)
    inputs = [args.base / name for name in ("train.jsonl.gz", "coverage.json", "manifest.json")]
    database = args.base / "consolidated/identities.sqlite"
    inputs += args.supplement + protected + args.protect_queue + [database]
    inputs += sorted(
        {
            p.parent / "manifest.json"
            for p in args.supplement
            if (p.parent / "manifest.json").exists()
        }
    )
    checksums = {str(p.resolve()): file_sha256(p) for p in inputs}
    counts = Counter()
    supplements, conflicts = {}, set()
    with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as db:
        for path in args.supplement:
            for row in rows(path):
                counts["supplement_occurrences"] += 1
                if row.get("annotation_status") != "accepted":
                    raise ValueError("Supplement contains a row without explicit admission")
                validate(row)
                item = encode(row)
                if item is None or components(item[1], item[2], row["text"]) != item[3]["components"]:
                    raise ValueError("Supplement cannot round-trip exact spans")
                model_input, labels = digest(json.dumps(item[0])), digest(json.dumps(item[1]))
                existing = db.execute(
                    "SELECT model_labels,reason FROM identities WHERE model_input=?",
                    (model_input,),
                ).fetchall()
                if (
                    identity(row["text"]) in protected_text
                    or street_keys(row) & protected_streets
                    or model_input in protected_model
                ):
                    counts["supplement_protected"] += 1
                    continue
                if any(reason or label != labels for label, reason in existing):
                    counts["supplement_base_conflict_or_quarantine"] += 1
                    continue
                if existing:
                    counts["supplement_base_model_duplicate"] += 1
                    continue
                if model_input in supplements:
                    if supplements[model_input][0] != labels:
                        conflicts.add(model_input)
                    counts["supplement_internal_model_duplicate"] += 1
                else:
                    supplements[model_input] = (labels, row)
    counts["supplement_internal_conflicting_inputs"] = len(conflicts)
    indexes = defaultdict(lambda: array("Q"))
    base_counts = Counter()
    with tempfile.TemporaryFile(dir=args.output) as spool:

        def append(row):
            row = dict(row, split="train", training_admission=True)
            indexes[key(row)].append(spool.tell())
            spool.write((json.dumps(row, ensure_ascii=False) + "\n").encode())

        for row in rows(args.base / "train.jsonl.gz"):
            append(row)
            base_counts[key(row)] += 1
        if dict(base_counts) != reference:
            raise ValueError("Base rows differ from reference coverage")
        supplement_start = spool.tell()
        for model_input, (_, row) in supplements.items():
            if model_input not in conflicts:
                append(row)
                counts["supplement_unique_available"] += 1
        new_strata = set(indexes) - set(reference)
        if new_strata:
            raise ValueError(f"New strata need an explicit reference weight: {sorted(new_strata)}")
        spool.flush()
        rng = random.Random(args.seed)
        exposures = Counter()
        supplement_exposures = Counter()
        with (
            (args.output / "train.jsonl.gz").open("xb") as raw_output,
            gzip.GzipFile(
                filename="", fileobj=raw_output, mode="wb", compresslevel=1, mtime=0
            ) as output,
        ):
            for stratum, count in sorted(allocation.items()):
                pool = indexes[stratum]
                # Exhaust a stratum before repeating it; avoid wasting budget on duplicates.
                remaining = count
                while remaining:
                    selected = rng.sample(pool, min(len(pool), remaining))
                    for offset in selected:
                        spool.seek(offset)
                        output.write(spool.readline())
                        exposures[stratum] += 1
                        supplement_exposures[stratum] += offset >= supplement_start
                    remaining -= len(selected)
        available = {k: len(v) for k, v in indexes.items()}
    for name in ("dev.jsonl.gz", "test.jsonl.gz"):
        shutil.copyfile(args.base / name, args.output / name)
    report = dict(
        status="fixed-budget experimental exposure; repeated rows intentional, not unique corpus size",
        sampling="without replacement within each stratum cycle; square-root frozen baseline country/address-type counts",
        seed=args.seed,
        rows=args.rows,
        inputs=checksums,
        code_sha256=file_sha256(Path(__file__)),
        reference_counts=reference,
        available_unique_pool_counts=available,
        exposure_counts=dict(exposures),
        supplement_exposure_counts=dict(supplement_exposures),
        unique_pool_rows_exposed=sum(min(available[k], n) for k, n in allocation.items()),
        supplement_counts=dict(counts),
        limitations=[
            "Weights are a controlled hypothesis, not population frequencies or an optimum.",
            "Base retention and raw source reservoirs remain unchanged.",
            "Supplement deduplication uses model-input identity, not physical-premise identity.",
            "The same materialized exposure repeats across epochs; no full-reservoir coverage claim.",
            "Additional protection queues block new supplements only; inherited base overlaps remain historical exposure.",
        ],
    )
    report["outputs"] = {
        name: file_sha256(args.output / name)
        for name in ("train.jsonl.gz", "dev.jsonl.gz", "test.jsonl.gz")
    }
    (args.output / "manifest.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(dict(rows=args.rows, supplement_counts=counts)))


if __name__ == "__main__":
    main()
