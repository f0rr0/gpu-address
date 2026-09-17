"""Freeze experimental.3 evidence; reuse existing inputs and comparator predictions.

uv run --with usaddress==0.5.16 python packages/training/scripts/release_us_evidence.py
Requires the local selected checkpoint and frozen spot-check artifacts.
"""

import hashlib
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import brotli
import torch
import usaddress  # ty: ignore[unresolved-import]  # Optional comparator: uv run --with usaddress
from audit_website_benchmark import fields
from training.data import batch
from training.export import serialize
from training.model import Tagger
from training.tokenizer import components, encode
from usaddress_benchmark import score

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "runs/ordered-h128-us-robustness-int5-20260917"
PUBLIC = ROOT / "apps/website/public"
OUT = PUBLIC / "evaluation-us-v1"


def digest(value):
    return hashlib.sha256(value).hexdigest()


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def main():
    checkpoint = torch.load(RUN / "best.pt", map_location="cpu", weights_only=False)
    model = Tagger(**checkpoint["metadata"]["config"])
    model.load_state_dict(checkpoint["model"])
    blob, model, _ = serialize(model, quantized=True, bits=5)
    assert digest(blob) == "06a212f708a52c32e099c15e384e3bd149885c01d06c4b00343cc3b7ad894b60"
    model = model.to("mps").eval()
    OUT.mkdir(exist_ok=True)
    prior = PUBLIC / "evaluation-v4"
    rows = [r for r in json.loads((prior / "inputs.json").read_text()) if r["country"] == "us"]
    assert len(rows) == 842 and all(r["cohort"] == "complete" for r in rows)
    predictions = {}
    for start in range(0, len(rows), 64):
        encoded = [encode(r, labeled=False, gap_features=True) for r in rows[start : start + 64]]
        assert all(item is not None for item in encoded)
        x, _, lengths, ordered = batch(encoded, "mps")
        with torch.inference_mode():
            paths = model.decode(model(x, lengths), lengths)
        predictions.update(
            {r[3]["id"]: components(path, r[2], r[3]["text"]) for path, r in zip(paths, ordered)}
        )
    save("nad-inputs.json", rows)
    save("nad-gpu.json", predictions)
    scores = {"gpu": score(rows, predictions)}
    for name in ("usaddress", "libpostal", "senzing", "deepparse"):
        cached = json.loads((prior / f"{name}.json").read_text())
        assert all(r["id"] in cached for r in rows)
        scores[name] = score(rows, cached)
    assert scores["usaddress"]["correct"] == 831

    source = json.loads((RUN / "spot-checks-final/results.json").read_text())
    counts = defaultdict(Counter)
    evidence = []
    for row in source:
        actual = {"gpu": row["predictions"]["final"], "usaddress": row["predictions"]["usaddress"]}
        c = counts[row["cohort"]]
        c["rows"] += 1
        for name, parts in actual.items():
            c[name] += fields(parts) == fields(row["components"])
        evidence.append(
            {k: row[k] for k in ("id", "text", "components", "cohort")}
            | {
                "source": row.get("source"),
                "parent_id": row.get("parent_id"),
                "predictions": actual,
            }
        )
    expected = json.loads((RUN / "spot-checks-final/report.json").read_text())
    assert expected["int5_sha256"] == digest(blob)
    for cohort, c in counts.items():
        assert c["gpu"] == expected["cohorts"][cohort]["final"]
        assert c["usaddress"] == expected["cohorts"][cohort]["usaddress"]
    save("diagnostic-predictions.json", evidence)
    shutil.copyfile(
        ROOT / "data/us-robustness-int5-20260917/us50-LICENSE.md", OUT / "us50-LICENSE.md"
    )
    shutil.copyfile(RUN / "browser-qualification/browser-result.json", OUT / "browser-parity.json")
    usbytes = Path(usaddress.MODEL_PATH).read_bytes()
    assert digest(usbytes) == "37ea2e93ece3b9340b4da455839ded8bb11a6c6ecaccfc3c8f80ed922f5065d9"
    sizes = {
        "gpu": {"bytes": len(brotli.compress(blob, quality=11)), "sha256": digest(blob)},
        "usaddress": {
            "bytes": len(brotli.compress(usbytes, quality=11)),
            "sha256": digest(usbytes),
        },
    }
    runtime = sum(
        len(brotli.compress(p.read_bytes(), quality=11))
        for p in (ROOT / "packages/core/dist").glob("*.js")
    )
    natural = json.loads((RUN / "comparison-test.json").read_text())["panels"]["natural-diagnostic"]
    report = {
        "release": "0.1.0-experimental.3",
        "checkpoint_epoch": 20,
        "model_sha256": digest(blob),
        "checkpoint_sha256": digest((RUN / "best.pt").read_bytes()),
        "nad": {"country": "us", "cohort": "complete", "rows": len(rows), "models": scores},
        "diagnostics": dict(counts),
        "us50": natural,
        "sizes": sizes,
        "runtime_brotli": runtime,
        "model_and_runtime_brotli": sizes["gpu"]["bytes"] + runtime,
        "compression": "Brotli quality 11, each file separately. Size chart excludes runtimes for both models; usaddress requires Python, CRFsuite and feature extraction.",
        "nad_method": "Same frozen v4 US NAD inputs, current int5 predictions, cached competitors. Four-field token multisets: locality joins street, district joins state. Training overlap with the expanded US corpus and competitors is unknown; not a newly blind benchmark.",
        "diagnostic_method": "Seven-field token multisets, no locality/district merging; case, commas and whitespace ignored. Derived presentations share 20 official-source institutional addresses. Labels authored before pilot inference. Not independent traffic samples or population accuracy. Historical US50 sample is separate.",
        "us50_method": "Historical usaddress upstream test; coarse-field mapping; 16 exact training overlaps. Entity and competitor exposure unknown.",
        "prior_comparators": "/evaluation-v4/",
        "hashes": {
            p.name: digest(p.read_bytes())
            for p in sorted(OUT.glob("*.json"))
            if p.name != "results.json"
        },
    }
    save("results.json", report)
    print(
        json.dumps(
            {
                "nad": {k: v["percent"] for k, v in scores.items()},
                "sizes": sizes,
                "runtime": runtime,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
