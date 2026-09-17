"""Frozen, disk-backed US expansion; source admission precedes exposure selection."""

import argparse
import gzip
import json
import re
import sqlite3
import time
import unicodedata
import zlib
from collections import Counter, defaultdict
from pathlib import Path

import pyarrow.compute as pc
import pyarrow.parquet as pq
import pyogrio
from training.consolidate import rows
from training.expand import file_sha256, hf_row, render, street_keys
from training.prepare import digest, group, identity, write_rows
from training.schema import seven_fields
from training.tokenizer import components, encode

BASE = Path("data/english-seven-20260916")
RAW = Path("data/latin-20260915/raw")
ORIGINALS = [
    Path("data/latin-20260915/diagnostic-v4/train.jsonl.gz"),
    Path("data/latin-20260915/us-gb-expansion-v1/candidates.jsonl.gz"),
]
STATES = dict(
    zip(
        "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split(),
        "Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming|District of Columbia".split(
            "|"
        ),
    )
)
STATE_KEYS = {identity(v): k for k, v in STATES.items()} | {k.lower(): k for k in STATES}


def text_key(text):
    return digest(re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text).casefold()).strip())


def unpack(payload):
    return json.loads(zlib.decompress(payload) if isinstance(payload, bytes) else payload)


def split_for(key):
    value = int(digest("english-seven-v1|" + key)[:8], 16) % 100
    return "dev" if value < 5 else "test" if value < 10 else "train"


def keys(row):
    row = dict(row, country=row.get("country", "us").lower())
    fields = defaultdict(list)
    for p in row["components"]:
        fields[p["label"]].append(identity(p["raw"]))
    fine = any(p["label"] == "road" for p in row["components"])
    street = " ".join(fields["road"] if fine else fields["street_address"])
    # Also protect exact street-address entities when external annotations are merged.
    aliases = set(street_keys(row))
    if street:
        for label in ("city", "postcode"):
            if fields[label]:
                aliases.add(
                    digest(row["country"] + "|entity|" + street + "|" + " ".join(fields[label]))
                )
    return aliases


def kind(row):
    labels = {p["label"] for p in row["components"]}
    if labels & {"unit", "level", "house", "entrance", "staircase"}:
        return 0
    if "po_box" in labels:
        return 1
    if "road" in labels and "house_number" not in labels:
        return 2
    if "road" in labels:
        return 3
    return 4


def log(**values):
    print(json.dumps(values), flush=True)


def initialize(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS done (stage TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS originals (key TEXT PRIMARY KEY, id TEXT, split TEXT,
            payload TEXT, enriched INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS protected (key TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS groups (key TEXT PRIMARY KEY, split TEXT);
        CREATE TABLE IF NOT EXISTS new_groups (key TEXT PRIMARY KEY, split TEXT);
        CREATE TABLE IF NOT EXISTS entities (key TEXT PRIMARY KEY, candidate TEXT);
        CREATE TABLE IF NOT EXISTS candidates (key TEXT PRIMARY KEY, signature TEXT,
            state TEXT, kind INTEGER, grp TEXT, split TEXT, novel INTEGER,
            rank TEXT, payload TEXT, conflict INTEGER DEFAULT 0);
    """)


def seed(db):
    if db.execute("SELECT 1 FROM done WHERE stage='seed'").fetchone():
        return
    db.execute("ATTACH DATABASE ? AS old", (str(BASE / "identities.sqlite"),))
    # The initial copy is one committed transaction: an existing row means it finished.
    if not db.execute("SELECT 1 FROM originals LIMIT 1").fetchone():
        db.execute("""INSERT INTO originals(key,id,split,payload)
            SELECT key,json_extract(payload,'$.id'),split,payload FROM old.rows WHERE conflict=0""")
        db.commit()
    log(stage="seed-enrichment-start")
    recovered = 0
    for source in ORIGINALS:
        for index, row in enumerate(rows(source)):
            if row.get("country") not in {"us", "gb", "au", "nz", "ca", "ie", "za"}:
                continue
            key = text_key(row["text"])
            old = db.execute(
                "SELECT id,split,payload FROM originals WHERE key=? AND enriched=0", (key,)
            ).fetchone()
            if old is None or old[0] != row["id"]:
                continue
            projected = seven_fields(row)
            saved = json.loads(old[2])
            if projected["components"] != saved["components"]:
                raise ValueError("Original annotations no longer match admitted corpus")
            saved.update(source_components=row["components"], group_key=group(row))
            db.execute(
                "UPDATE originals SET payload=?,enriched=1 WHERE key=?",
                (json.dumps(saved, ensure_ascii=False), key),
            )
            for alias in keys(row) | keys(projected) | {group(row)}:
                previous = db.execute("SELECT split FROM groups WHERE key=?", (alias,)).fetchone()
                split = old[1]
                # Conservative: any old heldout membership protects the entire alias.
                if previous and previous[0] != "train":
                    split = previous[0]
                db.execute("INSERT OR REPLACE INTO groups VALUES (?,?)", (alias, split))
            db.execute("INSERT OR IGNORE INTO protected VALUES (?)", (identity(row["text"]),))
            recovered += 1
            if recovered % 100000 == 0:
                db.commit()
                log(stage="seed", recovered=recovered)
    missing = db.execute("SELECT COUNT(*) FROM originals WHERE enriched=0").fetchone()[0]
    if missing:
        raise ValueError(f"Could not recover {missing} admitted source rows")
    protected_files = [
        Path("data/competitor-comparison-20260916/inputs.jsonl"),
        Path("data/multisource/public-benchmark.jsonl.gz"),
    ]
    for path in protected_files:
        for row in rows(path):
            db.execute("INSERT OR IGNORE INTO protected VALUES (?)", (identity(row["text"]),))
            projected = seven_fields(row) if all("start" in p for p in row["components"]) else row
            for alias in keys(row) | keys(projected):
                db.execute("INSERT OR REPLACE INTO groups VALUES (?, 'protected')", (alias,))
    for path in (
        Path("data/geosearch-sample-20260916/inputs.json"),
        Path("data/website-benchmark/inputs.json"),
    ):
        data = json.loads(path.read_text())
        entries = data if isinstance(data, list) else data.get("rows", data.get("inputs", []))
        for row in entries:
            db.execute("INSERT OR IGNORE INTO protected VALUES (?)", (identity(row["text"]),))
            if "components" in row:
                for alias in keys(row):
                    db.execute("INSERT OR REPLACE INTO groups VALUES (?, 'protected')", (alias,))
    db.execute("INSERT INTO done VALUES ('seed')")
    db.commit()
    log(stage="seed-complete", recovered=recovered)


def admit(db, row, counters):
    counters["mapped"] += 1
    projected = seven_fields(row)
    item = encode(projected)
    if item is None or components(item[1], item[2], row["text"]) != projected["components"]:
        counters["encoding_rejected"] += 1
        return
    key = text_key(row["text"])
    if db.execute("SELECT 1 FROM protected WHERE key=?", (identity(row["text"]),)).fetchone():
        counters["existing_or_protected"] += 1
        return
    aliases = keys(row) | keys(projected) | {group(row)}
    memberships = {
        p[0]
        for alias in aliases
        if (p := db.execute("SELECT split FROM groups WHERE key=?", (alias,)).fetchone())
    }
    if memberships - {"train"}:
        counters["heldout_group"] += 1
        return
    grp = group(row)
    new_memberships = {
        p[0]
        for alias in aliases
        if (p := db.execute("SELECT split FROM new_groups WHERE key=?", (alias,)).fetchone())
    }
    if len(new_memberships) > 1 or (memberships and new_memberships - {"train"}):
        counters["cross_source_split_bridge"] += 1
        return
    split = "train" if "train" in memberships else next(iter(new_memberships), split_for(grp))
    category = kind(row)
    labels = {p["label"] for p in projected["components"]}
    if category == 4 and ("street_address" in labels or len(labels - {"country"}) < 2):
        counters["unsafe_partial"] += 1
        return
    state = next(
        (
            STATE_KEYS.get(identity(p["raw"]), "unknown")
            for p in row["components"]
            if p["label"] == "state"
        ),
        "unknown",
    )
    signature = json.dumps([(p["label"], identity(p["raw"])) for p in projected["components"]])
    old = db.execute("SELECT signature FROM candidates WHERE key=?", (key,)).fetchone()
    if old:
        counters["duplicate"] += 1
        if old[0] != signature:
            db.execute("UPDATE candidates SET conflict=1 WHERE key=?", (key,))
        return
    entity = digest(
        json.dumps(sorted((p["label"], identity(p["raw"])) for p in projected["components"]))
    )
    if db.execute("SELECT 1 FROM entities WHERE key=?", (entity,)).fetchone():
        counters["duplicate"] += 1
        return
    projected.update(source_components=row["components"], group_key=grp, split=split)
    db.execute(
        "INSERT INTO candidates VALUES (?,?,?,?,?,?,?,?,?,0)",
        (
            key,
            signature,
            state,
            category,
            grp,
            split,
            int(not memberships),
            digest("2026|" + row["id"]),
            zlib.compress(json.dumps(projected, ensure_ascii=False).encode(), level=1),
        ),
    )
    counters["admitted"] += 1
    db.execute("INSERT INTO entities VALUES (?,?)", (entity, key))
    for alias in aliases:
        db.execute("INSERT OR IGNORE INTO new_groups VALUES (?,?)", (alias, split))


def scan_hf(db):
    policy = json.loads(Path("data/latin-20260915/us-gb-expansion-v1/report.json").read_text())[
        "approval"
    ]["value"]["countries"]["us"]
    for i in range(4):
        stage = f"us-{i}"
        if db.execute("SELECT 1 FROM done WHERE stage=?", (stage,)).fetchone():
            continue
        path = RAW / f"us-chunk-{i}.parquet.raw"
        receipt = json.loads(path.with_suffix(".json").read_text())
        if file_sha256(path) != receipt["sha256"]:
            raise ValueError(f"Source hash mismatch: {path}")
        counters, offset = Counter(), 0
        for b in pq.ParquetFile(path).iter_batches(batch_size=65536):
            mask = pc.is_in(  # ty: ignore[unresolved-attribute]
                b.column("Language"), value_set=__import__("pyarrow").array(["eng", "en"])
            )
            positions = pc.indices_nonzero(mask).to_pylist()  # ty: ignore[unresolved-attribute]
            for position, record in zip(positions, b.filter(mask).to_pylist()):
                counters["english"] += 1
                if "District" in record["Tags"]:
                    counters["blocked_tag"] += 1
                    continue
                try:
                    row = hf_row(record, "us")
                    for part in row["components"]:
                        if part["label"] == "unit" and re.search(
                            policy["unit_floor_signal_regex"], part["raw"]
                        ):
                            if not re.fullmatch(policy["unit_pure_floor_regex"], part["raw"]):
                                raise ValueError("mixed-floor-unit")
                            part["label"] = "level"
                        for rule in policy["blocked_component_regexes"]:
                            if (
                                "label" not in rule or part["label"] == rule["label"]
                            ) and re.search(rule["regex"], part["raw"]):
                                raise ValueError("blocked-component")
                    row.update(
                        id=f"{receipt['sha256']}:{offset + position}",
                        source=f"us/chunk-{i}.parquet",
                    )
                    admit(db, row, counters)
                except (ValueError, KeyError):
                    counters["mapping_rejected"] += 1
            offset += b.num_rows
            db.commit()
            log(stage=stage, scanned=offset, counts=dict(counters))
        db.execute("INSERT INTO done VALUES (?)", (stage,))
        db.commit()


def scan_texas(db):
    if db.execute("SELECT 1 FROM done WHERE stage='texas'").fetchone():
        return
    path = RAW / "texas-addresspoints-2025.zip"
    sha = file_sha256(path)
    source = "/vsizip/" + str(path.resolve()) + "/stratmap25-addresspoints_48.gdb"
    counters, offset = Counter(), 0
    street_fields = (
        "St_PreMod St_PreDir St_PreTyp St_PreSep St_Name St_PosTyp St_PosDir St_PosMod".split()
    )
    columns = [
        "Add_Number",
        "AddNum_Suf",
        *street_fields,
        "Unit",
        "Post_Comm",
        "State",
        "Post_Code",
    ]
    with pyogrio.open_arrow(
        source, columns=columns, read_geometry=False, use_pyarrow=True, batch_size=65536
    ) as (_, reader):
        for batch in reader:
            for record in batch.to_pylist():
                offset += 1
                clean = {k: str(v).strip() if v is not None else "" for k, v in record.items()}
                values = [
                    (
                        "house_number",
                        " ".join(clean[k] for k in ["Add_Number", "AddNum_Suf"] if clean[k]),
                    ),
                    ("road", " ".join(clean[k] for k in street_fields if clean[k])),
                    ("unit", clean["Unit"]),
                    ("city", clean["Post_Comm"]),
                    ("state", clean["State"]),
                    ("postcode", clean["Post_Code"]),
                ]
                if not clean["St_Name"] or clean["State"] != "TX":
                    counters["invalid"] += 1
                    continue
                row = render(values, "us", str(offset))
                row.update(id=f"{sha}:{offset}", source="openaddresses/tx/2025")
                try:
                    admit(db, row, counters)
                except (ValueError, KeyError):
                    counters["mapping_rejected"] += 1
            db.commit()
            log(stage="texas", scanned=offset, counts=dict(counters))
    db.execute("INSERT INTO done VALUES ('texas')")
    db.commit()


def finish(db, output):
    if (output / "manifest.json").exists():
        raise ValueError("Output manifest already exists")
    # Window ranks implement group-first, type-round-robin, state-round-robin exposure.
    db.executescript("""
        CREATE TABLE selected AS
        WITH g AS (SELECT key,split,state,kind,grp,novel,rank, ROW_NUMBER() OVER(PARTITION BY split,state,kind,grp ORDER BY rank) AS gr
                   FROM candidates WHERE conflict=0),
        t AS (SELECT *, ROW_NUMBER() OVER(PARTITION BY split,state,kind ORDER BY gr,novel DESC,rank) AS tr FROM g),
        s AS (SELECT *, ROW_NUMBER() OVER(PARTITION BY split,state ORDER BY tr,kind,rank) AS sr FROM t)
        SELECT key,split,state,gr,sr,rank FROM s ORDER BY split,sr,state;
    """)
    counts, sources = defaultdict(Counter), defaultdict(Counter)
    for split in ("train", "dev", "test"):
        target = output / f"{split}{'-all' if split != 'train' else ''}.jsonl.gz"
        with gzip.open(target, "xt", compresslevel=1) as stream:
            for (payload,) in db.execute("SELECT payload FROM originals WHERE split=?", (split,)):
                row = json.loads(payload)
                stream.write(payload + "\n")
                counts[split][row["country"]] += 1
                sources[split][row.get("source") or "unknown"] += 1
            limit = 3_000_000 if split == "train" else 100_000
            for (payload,) in db.execute(
                "SELECT c.payload FROM selected s JOIN candidates c ON c.key=s.key WHERE s.split=? ORDER BY s.sr,s.state LIMIT ?",
                (split, limit),
            ):
                row = unpack(payload)
                row["expansion"] = True
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                counts[split]["us"] += 1
                sources[split][row["source"]] += 1
        log(stage="written", split=split, counts=dict(counts[split]))
    for split in ("dev", "test"):
        old_ids = {r["id"] for r in rows(BASE / f"{split}.jsonl.gz")}
        old = []
        for (payload,) in db.execute("SELECT payload FROM originals WHERE split=?", (split,)):
            row = json.loads(payload)
            if row["id"] in old_ids:
                old.append(row)
        new = [
            unpack(p[0])
            for p in db.execute(
                "SELECT c.payload FROM selected s JOIN candidates c ON c.key=s.key WHERE s.split=? ORDER BY s.gr,s.rank LIMIT 2000",
                (split,),
            )
        ]
        write_rows(output / f"{split}-old-us.jsonl.gz", [r for r in old if r["country"] == "us"])
        write_rows(output / f"{split}-new-us.jsonl.gz", new)
        write_rows(output / f"{split}.jsonl.gz", old + new)
    manifest = dict(
        status="originals-ready-panels-pending",
        split_countries={k: dict(v) for k, v in counts.items()},
        sources={k: dict(v) for k, v in sources.items()},
        inputs={
            str(p): file_sha256(p)
            for p in ORIGINALS
            + sorted(RAW.glob("us-chunk-*.parquet.raw"))
            + [RAW / "texas-addresspoints-2025.zip", BASE / "manifest.json"]
        },
        outputs={p.name: file_sha256(p) for p in output.glob("*.gz")},
        code_sha256=file_sha256(Path(__file__)),
        source_scan=json.loads((output / "pool-frozen.json").read_text())
        if (output / "pool-frozen.json").exists()
        else {"complete": True},
        created=time.time(),
    )
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--stage", choices=["seed", "sources", "finish", "all"], default="all")
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(args.output / "selection.sqlite") as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=NORMAL")
        db.execute("PRAGMA cache_size=-1048576")
        db.execute("PRAGMA mmap_size=1073741824")
        initialize(db)
        if args.stage in {"seed", "all"}:
            seed(db)
        frozen = (args.output / "pool-frozen.json").exists()
        if args.stage in {"sources", "all"} and not frozen:
            if not db.execute("SELECT 1 FROM done WHERE stage='seed'").fetchone():
                raise ValueError("Seed original split protections first")
            scan_hf(db)
            scan_texas(db)
        if args.stage in {"finish", "all"}:
            if not db.execute("SELECT 1 FROM done WHERE stage='seed'").fetchone():
                raise ValueError("Original split protections must be complete")
            if not frozen and db.execute("SELECT COUNT(*) FROM done").fetchone()[0] != 6:
                raise ValueError("All source scans must finish before selection")
            finish(db, args.output)


if __name__ == "__main__":
    main()
