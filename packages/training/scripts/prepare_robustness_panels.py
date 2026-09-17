"""Freeze robustness panels and training-only ambiguity exclusions before training."""

import argparse
import json
import random
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

import torch
from training.consolidate import rows
from training.data import ambiguity_key, load, partial_variants, render_parts, structural_variant
from training.evaluate import evaluate
from training.expand import file_sha256
from training.export import serialize
from training.model import Tagger
from training.prepare import digest, identity, write_rows
from training.tokenizer import components, encode
from training.train import ROBUST_PANELS

COUNTRIES = {"us"}
BASELINE = Path("runs/ordered-h128-english-seven-20260916/best.pt")
BASELINE_SHA = "436dc0a84fca3816a851f28a5eb56d716153acc993748ddc16768e7c6502e7ec"
MODEL_SHA = "e97cfb86c5ec703ad70ba684f2f373a44dc9c9e1018e517ab6799e74aa5ce84a"
CHALLENGE = Path("packages/training/tests/fixtures/robustness-challenge.jsonl")


def conflicts(directory):
    destination = directory / "augmentation-conflicts.json"
    if destination.exists():
        return set(json.loads(destination.read_text()))
    with sqlite3.connect(directory / "augmentation-identities.sqlite") as db:
        db.execute("PRAGMA cache_size=-65536")
        db.execute(
            "CREATE TABLE IF NOT EXISTS labels (key TEXT PRIMARY KEY, signature TEXT, conflict INTEGER DEFAULT 0)"
        )
        for i, row in enumerate(rows(directory / "train.jsonl.gz"), 1):
            # Do not consult dev/test labels. Sorting spans makes the check order-invariant.
            for candidate in [row, *partial_variants(row)]:
                signature = json.dumps(
                    sorted((p["label"], identity(p["raw"])) for p in candidate["components"])
                )
                db.execute(
                    """INSERT INTO labels VALUES (?,?,0) ON CONFLICT(key) DO UPDATE
                    SET conflict=1 WHERE signature != excluded.signature""",
                    (ambiguity_key(candidate), signature),
                )
            if i % 100000 == 0:
                db.commit()
                print(json.dumps(dict(stage="augmentation-conflicts", originals=i)), flush=True)
        db.commit()
        blocked = [r[0] for r in db.execute("SELECT key FROM labels WHERE conflict=1 ORDER BY key")]
    destination.write_text(json.dumps(blocked))
    return set(blocked)


def panels(directory, blocked):
    report = {}
    for split, seed in (("dev", 2027), ("test", 2028)):
        by_country = defaultdict(dict)
        for row in rows(directory / f"{split}.jsonl.gz"):
            key = row.get("group_key", row["id"])
            previous = by_country[row["country"]].get(key)
            if previous is None or digest(row["id"]) < digest(previous["id"]):
                by_country[row["country"]][key] = row
        counts = {}
        for mode in ("partial", "reordered", "combined", "zip-first"):
            selected = []
            for country in sorted(COUNTRIES):
                parents = sorted(
                    by_country[country].values(), key=lambda r: digest(f"{seed}|{r['id']}")
                )[:1000]
                for row in parents:
                    rng = random.Random(digest(f"{seed}|{mode}|{row['id']}"))
                    item = encode(row)
                    if mode == "zip-first":
                        parts = row["components"]
                        if not any(p["label"] == "postcode" for p in parts) or len(parts) < 2:
                            continue
                        ordered = [p for p in parts if p["label"] == "postcode"] + [
                            p for p in parts if p["label"] != "postcode"
                        ]
                        changed = encode(render_parts(row, ordered, ", "))
                        operation = mode
                    else:
                        changed, operation = structural_variant(item, rng, mode, blocked=blocked)
                    if operation != mode or changed[3]["text"] == row["text"]:
                        continue
                    value = dict(changed[3], id=f"{row['id']}:{mode}", slice=mode)
                    assert components(changed[1], changed[2], value["text"]) == value["components"]
                    selected.append(value)
            counts[mode] = dict(Counter(r["country"] for r in selected))
            if set(counts[mode]) != COUNTRIES:
                raise ValueError(f"Incomplete panel coverage: {split}/{mode}")
            write_rows(directory / f"{split}-{mode}.jsonl.gz", selected)
        report[split] = counts
    challenge = [r for r in rows(CHALLENGE) if r["country"] in COUNTRIES]
    assert Counter(r["country"] for r in challenge) == Counter(dict.fromkeys(COUNTRIES, 20))
    for row in challenge:
        item = encode(row)
        assert item is not None and components(item[1], item[2], row["text"]) == row["components"]
    report["challenge_sha256"] = file_sha256(CHALLENGE)
    (directory / "panels.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)


def baseline(directory):
    if file_sha256(BASELINE) != BASELINE_SHA:
        raise ValueError("Released checkpoint changed")
    checkpoint = torch.load(BASELINE, map_location="cpu", weights_only=False)
    model = Tagger(**checkpoint["metadata"]["config"])
    model.load_state_dict(checkpoint["model"])
    blob, deployed, _ = serialize(model, quantized=True, bits=5)
    import hashlib

    if hashlib.sha256(blob).hexdigest() != MODEL_SHA:
        raise ValueError("Int5 baseline differs from published model")
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    deployed.to(device)
    for split in ("dev", "test"):
        results = {}
        for name, filename in ROBUST_PANELS.items():
            path = directory / filename.replace("dev", split, 1)
            data, rejected = load(path)
            if rejected:
                raise ValueError(f"Unencodable panel: {path}")
            results[name] = evaluate(deployed, data, device, 128)
            print(
                json.dumps(
                    dict(
                        stage="baseline",
                        split=split,
                        panel=name,
                        exact=results[name]["exact"],
                        rows=results[name]["rows"],
                    )
                ),
                flush=True,
            )
        (
            directory / ("baseline-int5.json" if split == "dev" else "baseline-test-int5.json")
        ).write_text(json.dumps(results, indent=2))
    data = [encode(row) for row in rows(CHALLENGE) if row["country"] in COUNTRIES]
    if any(item is None for item in data):
        raise ValueError("Challenge has an unencodable row")
    rejected = 0
    (directory / "baseline-challenge-int5.json").write_text(
        json.dumps(evaluate(deployed, data, device, 128, unsupported=rejected), indent=2)
    )
    data, rejected = load(directory / "natural-diagnostic.jsonl.gz")
    (directory / "baseline-natural-int5.json").write_text(
        json.dumps(evaluate(deployed, data, device, 128, unsupported=rejected), indent=2)
    )
    manifest = json.loads((directory / "manifest.json").read_text())
    manifest.update(
        status="ready",
        baseline_checkpoint_sha256=BASELINE_SHA,
        baseline_model_sha256=MODEL_SHA,
        challenge_sha256=file_sha256(CHALLENGE),
    )
    manifest["outputs"].update({p.name: file_sha256(p) for p in directory.glob("*.jsonl.gz")})
    manifest["outputs"].update({p.name: file_sha256(p) for p in directory.glob("baseline*.json")})
    manifest["outputs"]["augmentation-conflicts.json"] = file_sha256(
        directory / "augmentation-conflicts.json"
    )
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, required=True)
    args = ap.parse_args()
    blocked = conflicts(args.data)
    panels(args.data, blocked)
    baseline(args.data)


if __name__ == "__main__":
    main()
