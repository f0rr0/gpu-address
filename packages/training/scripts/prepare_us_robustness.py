"""Reuse the frozen selection; no collection, resplitting, or new dependencies."""

import argparse
import json
import random
import shutil
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from training.consolidate import rows
from training.expand import file_sha256
from training.prepare import identity, write_rows
from training.schema import seven_fields
from training.tokenizer import components, encode

SOURCE = Path("data/robustness-int5-20260917")
DATA = Path("data/us-robustness-int5-20260917")
USADDRESS = Path("/tmp/usaddress-research.yU1OwH/usaddress")


def natural_diagnostic(directory):
    """Historical upstream test examples, not new gold or competitor-unseen data."""
    source = USADDRESS / "measure_performance/test_data/us50_test_tagged.xml"
    mapping = dict(PlaceName="city", StateName="state", ZipCode="postcode")
    street = {
        "StreetName",
        "AddressNumber",
        "LandmarkName",
        "USPSBoxID",
        "USPSBoxType",
        "OccupancyIdentifier",
        "OccupancyType",
        "USPSBoxGroupType",
        "IntersectionSeparator",
        "USPSBoxGroupID",
        "CornerOf",
    }
    result, seen = [], set()
    for i, address in enumerate(ET.parse(source).getroot()):
        text, spans = address.text or "", []
        for part in address:
            raw = part.text or ""
            start = len(text)
            text += raw
            label = mapping.get(part.tag, "street_address" if part.tag in street else None)
            if label is None and part.tag != "NotAddress":
                raise ValueError(f"Unmapped upstream label: {part.tag}")
            # Strip boundary separators, not internal punctuation or street abbreviations.
            left = len(raw) - len(raw.lstrip(" ,;\n\t"))
            end = len(text.rstrip(" ,;\n\t"))
            if label and end > start + left:
                spans.append(
                    dict(label=label, raw=text[start + left : end], start=start + left, end=end)
                )
            text += part.tail or ""
        row = seven_fields(
            dict(
                id=f"us50-test-{i}",
                country="us",
                text=text,
                components=spans,
                source="usaddress/us50_test_tagged.xml",
                split="diagnostic",
                label_provenance="upstream-labels; coarse projection",
            )
        )
        item = encode(row)
        if item is None or components(item[1], item[2], text) != row["components"]:
            raise ValueError(f"Unsupported upstream diagnostic: {i}")
        if identity(text) not in seen:
            result.append(row)
            seen.add(identity(text))
    write_rows(directory / "natural-diagnostic.jsonl.gz", result)
    shutil.copy2(source, directory / source.name)
    shutil.copy2(USADDRESS / "raw/LICENSE.md", directory / "us50-LICENSE.md")
    return result


def prepare():
    DATA.mkdir(parents=True, exist_ok=True)
    manifest_path = DATA / "manifest.json"
    if manifest_path.exists():
        raise ValueError("Prepared US corpus already exists; do not overwrite it")
    parent = json.loads((SOURCE / "manifest.json").read_text())
    natural = natural_diagnostic(DATA)
    diagnostic_keys = {identity(r["text"]) for r in natural}
    overlap = set()
    counts, pilot = Counter(), []
    rng = random.Random(2026)

    def selected():
        for row in rows(SOURCE / "train.jsonl.gz"):
            if row["country"] != "us":
                continue
            counts["us"] += 1
            key = identity(row["text"])
            if key in diagnostic_keys:
                overlap.add(key)
            # Reservoir is for the bounded pilot only; the full output retains every row.
            if len(pilot) < 200000:
                pilot.append(row)
            else:
                index = rng.randrange(counts["us"])
                if index < len(pilot):
                    pilot[index] = row
            if counts["us"] % 100000 == 0:
                print(json.dumps(dict(stage="us-filter", rows=counts["us"])), flush=True)
            yield row

    source_train = SOURCE / "train.jsonl.gz"
    if file_sha256(source_train) != parent["outputs"][source_train.name]:
        raise ValueError("Frozen parent training corpus changed")
    write_rows(DATA / "train.jsonl.gz", selected())
    assert counts["us"] == parent["split_countries"]["train"]["us"] == 3077917
    pilot_dir = DATA / "pilot"
    pilot_dir.mkdir(exist_ok=True)
    write_rows(pilot_dir / "train.jsonl.gz", pilot)
    for split in ("dev", "test"):
        for suffix in ("", "-old-us", "-new-us"):
            path = SOURCE / f"{split}{suffix}.jsonl.gz"
            if file_sha256(path) != parent["outputs"][path.name]:
                raise ValueError(f"Frozen parent panel changed: {path}")
            write_rows(DATA / path.name, (r for r in rows(path) if r["country"] == "us"))
    # Seen exact texts are disclosed rather than silently turned into 'unseen' evidence.
    report = dict(
        status="originals-ready-panels-pending",
        scope="US-only",
        split_countries={"train": dict(counts)},
        parent_manifest_sha256=file_sha256(SOURCE / "manifest.json"),
        parent=str(SOURCE),
        source_scan=parent["source_scan"],
        outputs={p.name: file_sha256(p) for p in DATA.glob("*.jsonl.gz")},
        natural_diagnostic=dict(
            rows=len(natural),
            exact_train_overlap=len(overlap),
            overlap_keys=sorted(overlap),
            upstream_commit="aa7699b53a0843fc443f9e87285b88cbd9eaf50a",
            source_sha256=file_sha256(DATA / "us50_test_tagged.xml"),
            limitation="Historical source-curated test; competitor exposure and entity overlap unknown. Not a representative natural-traffic benchmark.",
        ),
    )
    manifest_path.write_text(json.dumps(report, indent=2))
    pilot_report = dict(
        report,
        split_countries={"train": {"us": len(pilot)}},
        purpose="seed-2026 reservoir pilot, not the full training corpus",
        outputs={"train.jsonl.gz": file_sha256(pilot_dir / "train.jsonl.gz")},
    )
    (pilot_dir / "manifest.json").write_text(json.dumps(pilot_report, indent=2))
    print(json.dumps(dict(stage="us-prepared", train=counts["us"], pilot=len(pilot))), flush=True)


def pilot_panels():
    pilot = DATA / "pilot"
    for path in DATA.glob("*.jsonl.gz"):
        if path.name != "train.jsonl.gz":
            shutil.copy2(path, pilot / path.name)
    for name in (
        "augmentation-conflicts.json",
        "baseline-int5.json",
        "baseline-test-int5.json",
        "panels.json",
    ):
        shutil.copy2(DATA / name, pilot / name)
    manifest = json.loads((pilot / "manifest.json").read_text())
    manifest["outputs"].update({p.name: file_sha256(p) for p in pilot.glob("*.jsonl.gz")})
    manifest["status"] = "ready"
    (pilot / "manifest.json").write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pilot-panels", action="store_true")
    args = ap.parse_args()
    pilot_panels() if args.pilot_panels else prepare()
