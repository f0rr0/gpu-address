"""Frozen NAD / Companies House benchmark for the released model.

uv run python packages/training/scripts/broader_benchmark.py prepare|gpu|libpostal|senzing|report
PYTHONPATH=packages data/competitor-tools-20260916/venv/bin/python packages/training/scripts/broader_benchmark.py deep

Raw source snapshots stay in data/; published records contain address fields only.
No parser predictions are used in selection or gold construction.
"""

import argparse
import csv
import hashlib
import heapq
import io
import json
import random
import re
import sqlite3
import urllib.parse
import urllib.request
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import external_benchmark as external
import website_benchmark as harness

ROOT = harness.ROOT
DATA = ROOT / "data/broader-benchmark-20260917"
PUBLIC = ROOT / "apps/website/public/evaluation-v4"
SEED = "broader-v3-20260917"


def collect():
    """Download or reuse snapshots, then deterministically retain candidate records."""
    DATA.mkdir(exist_ok=True)
    url = "https://download.companieshouse.gov.uk/BasicCompanyDataAsOneFile-2026-09-01.zip"
    if not (DATA / "companies.zip").exists():
        with (
            urllib.request.urlopen(url, timeout=60) as response,
            (DATA / "companies.zip").open("wb") as out,
        ):
            while chunk := response.read(1024 * 1024):
                out.write(chunk)
    buckets, rejected = defaultdict(list), Counter()
    with (
        zipfile.ZipFile(DATA / "companies.zip") as archive,
        archive.open(archive.namelist()[0]) as stream,
    ):
        reader = csv.reader(io.TextIOWrapper(stream, encoding="utf-8-sig"))
        header = [k.strip() for k in next(reader)]
        indices = {k: i for i, k in enumerate(header)}
        address_fields = [k for k in header if k.startswith("RegAddress.")]
        for values in reader:
            if len(values) != len(header):
                rejected["malformed_csv_record"] += 1
                continue
            address = {k: values[indices[k]].strip() for k in address_fields}
            postcode = address["RegAddress.PostCode"].upper()
            if (
                not postcode
                or not address["RegAddress.PostTown"]
                or not address["RegAddress.AddressLine1"]
            ):
                rejected["missing_core_field"] += 1
                continue
            area = postcode.split()[0].rstrip("0123456789")
            if area in {"SY", "CH", "HR", "TD"}:
                rejected["cross_border_postcode_area"] += 1
                continue
            scotland = {
                "AB",
                "DD",
                "DG",
                "EH",
                "FK",
                "G",
                "HS",
                "IV",
                "KA",
                "KW",
                "KY",
                "ML",
                "PA",
                "PH",
                "TD",
                "ZE",
            }
            nation = (
                "Northern Ireland"
                if area == "BT"
                else "Scotland"
                if area in scotland
                else "Wales"
                if area in {"CF", "LL", "NP", "SA", "LD"}
                else "England"
            )
            ident = "ch:" + values[indices["CompanyNumber"]].strip()
            entry = (-int(hashlib.sha256((SEED + ident).encode()).hexdigest(), 16), ident, address)
            bucket = buckets[nation]
            if len(bucket) < 100:
                heapq.heappush(bucket, entry)
            elif entry > bucket[0]:
                heapq.heapreplace(bucket, entry)
    candidates = {
        k: [dict(id=i, source_fields=a) for _, i, a in sorted(v, reverse=True)]
        for k, v in buckets.items()
    }
    candidate_path = DATA / "companies-candidates.json"
    payload = json.dumps(candidates, indent=2)
    if candidate_path.exists():
        assert candidate_path.read_text() == payload, "Source candidate selection changed"
    else:
        candidate_path.write_text(payload)
    (DATA / "collection-exclusions.json").write_text(json.dumps(rejected, indent=2))
    # OID upper bound recorded from an indexed descending query in nad-max.json.
    identifiers = random.Random(SEED).sample(range(1, 102476026), 6000)
    base = "https://services.arcgis.com/xOi1kZaI0eWDREZv/ArcGIS/rest/services/Address_Points_from_National_Address_Database_view/FeatureServer/0/query"

    def download(index):
        path = DATA / f"nad-{index:02d}.json"
        if path.exists():
            return
        params = dict(
            f="json",
            objectIds=",".join(map(str, identifiers[index * 75 : (index + 1) * 75])),
            outFields="OBJECTID,AddNo_Full,StNam_Full,Building,Floor,Unit,Room,SubAddress,LandmkName,Post_City,Inc_Muni,Uninc_Comm,State,Zip_Code,Addr_Type,NAD_Source",
            returnGeometry="false",
        )
        with urllib.request.urlopen(
            base + "?" + urllib.parse.urlencode(params), timeout=40
        ) as response:
            raw = response.read()
        assert "features" in json.loads(raw)
        path.write_bytes(raw)

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(download, range(80)))


def prepare_baseline():
    if (PUBLIC / "manifest.json").exists():
        raise ValueError(
            "Frozen benchmark exists; use a new version, never overwrite its selection"
        )
    blocked = set()
    with sqlite3.connect(
        f"file:{ROOT}/data/english-seven-20260916/identities.sqlite?mode=ro", uri=True
    ) as db:
        for (payload,) in db.execute(
            "SELECT payload FROM rows WHERE split='train' AND conflict=0 AND country IN ('us','gb')"
        ):
            blocked.update(external.entity_keys(json.loads(payload)))
    for path in (
        ROOT / "data/website-benchmark/inputs.json",
        ROOT / "data/geosearch-sample-20260916/inputs.json",
        ROOT / "apps/website/public/evaluation/inputs.json",
    ):
        for row in json.loads(path.read_text()):
            blocked.update(external.entity_keys(dict(row, country=row.get("country", "us"))))
    pool, excluded, used = defaultdict(list), Counter(), set()

    def admit(row):
        keys = external.entity_keys(row)
        if keys & blocked:
            excluded["training_or_prior_evaluation_match"] += 1
        elif keys & used:
            excluded["duplicate_address"] += 1
        else:
            used.update(keys)
            pool[row["stratum"]].append(row)

    for path in sorted(DATA.glob("nad-[0-9]*.json")):
        for item in json.loads(path.read_text())["features"]:
            r = item["attributes"]
            required = [
                r.get(k) for k in ("AddNo_Full", "StNam_Full", "Post_City", "State", "Zip_Code")
            ]
            if not all(required) or any(
                re.search(r"not stated|unknown|<null>|unincorporated", str(v), re.I)
                for v in required
            ):
                excluded["NAD_missing_or_placeholder_core_field"] += 1
                continue
            if not re.fullmatch(r"\d{5}(?:-\d{4})?", r["Zip_Code"]):
                excluded["NAD_invalid_ZIP"] += 1
                continue
            # Use the typed subaddress fields when supplied; the aggregate is a fallback.
            sub = " ".join(
                f"{label} {r[k]}"
                for k, label in [
                    ("Building", "Building"),
                    ("Floor", "Floor"),
                    ("Unit", "Unit"),
                    ("Room", "Room"),
                ]
                if r.get(k)
            )
            sub = sub or r.get("SubAddress") or ""
            street = " ".join([r["AddNo_Full"], r["StNam_Full"], sub]).strip()
            row = external.render(
                "nad:" + str(r["OBJECTID"]),
                "us",
                r["State"],
                [
                    ("street_address", street),
                    ("city", r["Post_City"]),
                    ("state", r["State"]),
                    ("postcode", r["Zip_Code"]),
                ],
                path.name,
            )
            row.update(source_fields=r, has_subaddress=bool(sub), cohort="complete")
            admit(row)
    # These are source address-line labels, not invented fine-grained street labels.
    # The shared scoring projection groups locality into the address block for every parser.
    candidates = json.loads((DATA / "companies-candidates.json").read_text())
    for nation, rows in candidates.items():
        for item in rows:
            r = {k.removeprefix("RegAddress."): v for k, v in item["source_fields"].items()}
            if "COMPANIES HOUSE DEFAULT ADDRESS" in " ".join(r.values()).upper():
                excluded["CH_default_registration_address"] += 1
                continue
            if not re.fullmatch(r"[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}", r["PostCode"].upper()):
                excluded["CH_invalid_postcode"] += 1
                continue
            if re.match(r"^(CO[.\s]|COUNTY\s)", r["PostTown"], re.I):
                excluded["CH_county_in_town_field"] += 1
                continue
            lines = [r.get(k, "") for k in ("POBox", "AddressLine1", "AddressLine2") if r.get(k)]
            normalized = [external.key(v) for v in lines]
            if len(normalized) != len(set(normalized)) or external.key(r["PostTown"]) in normalized:
                excluded["CH_duplicate_address_line_or_town"] += 1
                continue
            if any(external.key(r["PostCode"]) in external.key(v) for v in lines):
                excluded["CH_postcode_in_address_line"] += 1
                continue
            values = [
                ("street_address", r.get("POBox", "")),
                ("street_address", r["AddressLine1"]),
                ("street_address", r["AddressLine2"]),
                ("city", r["PostTown"]),
                ("postcode", r["PostCode"]),
            ]
            row = external.render(item["id"], "gb", nation, values, "companies.zip")
            row.update(source_fields=item["source_fields"], cohort="complete")
            admit(row)
    selected = []
    import hashlib

    for stratum, rows in sorted(pool.items()):
        count = min(25, len(rows)) if rows[0]["country"] == "us" else 50
        if len(rows) < count:
            raise ValueError(f"Not enough eligible rows: {stratum}: {len(rows)}")
        selected.extend(
            sorted(rows, key=lambda r: hashlib.sha256((SEED + r["id"]).encode()).hexdigest())[
                :count
            ]
        )
    assert sum(r["country"] == "gb" for r in selected) == 200
    PUBLIC.mkdir(parents=True)
    (PUBLIC / "inputs.json").write_text(json.dumps(selected, indent=2, ensure_ascii=False))
    manifest = dict(
        protocol_version=3,
        frozen_at=datetime.now(timezone.utc).isoformat(),
        seed=SEED,
        rows=len(selected),
        entities=len(selected),
        cohorts=["complete"],
        selected=dict(Counter(r["stratum"] for r in selected)),
        eligible={k: len(v) for k, v in pool.items()},
        exclusions=dict(excluded),
        inputs_sha256=harness.sha(PUBLIC / "inputs.json"),
        preparation_sha256=harness.sha(Path(__file__)),
        model_sha256=harness.sha(ROOT / "packages/core/model.bin"),
        checkpoint_sha256=harness.sha(ROOT / "runs/ordered-h128-english-seven-20260916/best.pt"),
        models=json.loads((ROOT / "apps/website/public/benchmarks.json").read_text())["models"],
        field_projection={"locality": "street_address", "district": "state"},
        metric="Exact-field micro F1 and whole-address exact match. Source address block, town, region when present, postcode. Locality merged into address block; district merged into region for all parsers. NFKC/casefold token multisets ignore case/commas/whitespace, retain other punctuation and multiplicity. Extra fields penalized.",
        labels="Source-provided fields, not human-annotated token labels. NAD postal city only; no municipality substitution. UK AddressLine1/2 and POBox form one address block; CareOf, country and optional county omitted. All extra address lines retained. Source errors may remain; no claim of address validity.",
        selection="Before any inference: 6,000 seeded random NAD object IDs across 1..102476025; at most 25 eligible unique addresses per available state. Companies House full monthly snapshot: lowest 100 SHA256(seed+company ID) candidates per non-border postcode nation, then 50 eligible unique addresses per nation. Exclude ambiguous cross-border SY/CH/HR/TD postcode areas; equal UK nation weights are not population weights.",
        overlap="Exclude normalized street+town OR street+postcode matches against released-model training and all prior published evaluations. Near matches and competitor training overlap unknown; NAD may share upstream sources with OpenAddresses. The benchmark is author-run, not independently verified.",
        limitations="US NAD coverage is uneven; UK registered-office addresses only, not representative residential coverage. Structured fields rendered with commas, not natural user traffic. Four-field projection does not measure fine-grained locality/district extraction. FSA withheld because its untyped address lines need independent annotation. No synthetic deletion tests in primary results.",
        sources={
            name: dict(sha256=harness.sha(DATA / name))
            for name in [
                "companies.zip",
                "companies-candidates.json",
                "nad-max.json",
                *sorted(p.name for p in DATA.glob("nad-[0-9]*.json")),
            ]
        },
        source_urls={
            "companies.zip": "https://download.companieshouse.gov.uk/BasicCompanyDataAsOneFile-2026-09-01.zip",
            "nad": "https://services.arcgis.com/xOi1kZaI0eWDREZv/ArcGIS/rest/services/Address_Points_from_National_Address_Database_view/FeatureServer/0/query",
        },
        intervals="95% Wilson intervals for whole-address exact match; descriptive intervals for this selected sample, not national accuracy estimates.",
    )
    (PUBLIC / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (DATA / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps({k: manifest[k] for k in ("rows", "selected", "exclusions")}, indent=2))


def prepare():
    if (PUBLIC / "manifest.json").exists():
        raise ValueError("Frozen benchmark exists")
    previous = ROOT / "apps/website/public/evaluation-v3"
    manifest = json.loads((previous / "manifest.json").read_text())
    rows = json.loads((previous / "inputs.json").read_text())
    revised = []
    for row in rows:
        if row["country"] == "gb":
            source = row["source_fields"]
            values = [(p["label"], p["raw"]) for p in row["components"] if p["label"] != "postcode"]
            values.extend(
                [
                    ("state", source.get("RegAddress.County", "")),
                    ("postcode", source["RegAddress.PostCode"]),
                ]
            )
            row = dict(
                row,
                **external.render(row["id"], row["country"], row["stratum"], values, row["source"]),
            )
            row["has_county"] = bool(source.get("RegAddress.County"))
        revised.append(row)
    PUBLIC.mkdir(parents=True)
    (PUBLIC / "inputs.json").write_text(json.dumps(revised, indent=2, ensure_ascii=False))
    manifest.update(
        protocol_version=4,
        frozen_at=datetime.now(timezone.utc).isoformat(),
        inputs_sha256=harness.sha(PUBLIC / "inputs.json"),
        preparation_sha256=harness.sha(Path(__file__)),
        previous_inputs_sha256=manifest["inputs_sha256"],
        amendment="After observing v3 scores, restore all source-provided UK counties previously omitted. Same 1,042 selected entities; no prediction-based exclusions, relabeling or address selection. Report UK county-present and county-absent strata separately. v3 evidence retained.",
        labels="Source-provided registry fields, not human-annotated token gold. NAD postal city only. UK AddressLine1/2 and POBox form an address block; source County retained as region when present. CareOf and country omitted. Source field errors may remain; this measures agreement with registry fields, not address validity.",
    )
    (PUBLIC / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (DATA / "manifest-v4.json").write_text(json.dumps(manifest, indent=2))
    print(
        "Frozen",
        len(revised),
        "addresses; UK with county:",
        sum(r.get("has_county", False) for r in revised),
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "mode",
        choices=[
            "collect",
            "prepare-baseline",
            "prepare",
            "gpu",
            "libpostal",
            "senzing",
            "deep",
            "report",
        ],
    )
    mode = ap.parse_args().mode
    if mode == "collect":
        collect()
    elif mode == "prepare-baseline":
        PUBLIC = ROOT / "apps/website/public/evaluation-v3"
        prepare_baseline()
    elif mode == "prepare":
        prepare()
    else:
        manifest = json.loads((PUBLIC / "manifest.json").read_text())
        assert harness.sha(PUBLIC / "inputs.json") == manifest["inputs_sha256"]
        assert harness.sha(ROOT / "packages/core/model.bin") == manifest["model_sha256"]
        rows = json.loads((PUBLIC / "inputs.json").read_text())
        if mode == "report":
            # Existing scorer reads model.json; retain v3 predictions alongside v4.
            predictions_dir = DATA / "predictions-v4"
            predictions_dir.mkdir(exist_ok=True)
            for model in external.MODELS:
                (predictions_dir / f"{model}.json").write_bytes(
                    (DATA / f"{model}-v4.json").read_bytes()
                )
            external.DATA, external.PUBLIC = predictions_dir, PUBLIC
            external.report(rows, manifest)
        else:
            result = (
                harness.deep(rows)
                if mode == "deep"
                else harness.gpu(rows)
                if mode == "gpu"
                else harness.postal(rows, mode)
            )
            (DATA / f"{'deepparse' if mode == 'deep' else mode}-v4.json").write_text(
                json.dumps(result, indent=2)
            )
