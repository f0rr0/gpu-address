"""One frozen-checkpoint stress review. No fitting, checkpoint selection, or publication."""

import itertools
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any

import brotli
import torch
import usaddress  # ty: ignore[unresolved-import]  # Optional comparator: uv run --with usaddress
from training.consolidate import rows
from training.data import batch, render_parts
from training.expand import file_sha256
from training.export import export_model, serialize
from training.model import Tagger
from training.prepare import identity
from training.tokenizer import components, encode
from training.train import ROBUST_PANELS
from usaddress_benchmark import LABELS, projected

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data/us-robustness-int5-20260917"
RUN = ROOT / "runs/ordered-h128-us-robustness-pilot-20260917"
OUT = RUN / "evaluation-epoch24"
RELEASE = ROOT / "runs/ordered-h128-english-seven-20260916/best.pt"


def load_model(path, quantized):
    checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    model = Tagger(**checkpoint["metadata"]["config"])
    model.load_state_dict(checkpoint["model"])
    blob, model, _ = serialize(model, quantized=quantized, bits=5)
    return blob, model.to("mps").eval()


def predict(model, values):
    encoded = [encode(r, labeled=False, gap_features=model.config["gap_features"]) for r in values]
    assert all(item is not None for item in encoded), "Do not silently exclude unsupported inputs"
    x, _, lengths, ordered = batch(encoded, "mps")
    with torch.inference_mode():
        paths = model.decode(model(x, lengths), lengths)
    return {
        item[3]["id"]: components(path, item[2], item[3]["text"])
        for path, item in zip(paths, ordered)
    }


def main():
    OUT.mkdir(exist_ok=True)
    frozen = RUN / "epoch-24.pt"
    models = {}
    blobs = {}
    for name, path, quantized in (
        ("release", RELEASE, True),
        ("pilot", frozen, True),
        ("float32", frozen, False),
    ):
        blobs[name], models[name] = load_model(path, quantized)
    report: dict[str, Any] = dict(
        checkpoint=str(frozen),
        checkpoint_sha256=file_sha256(frozen),
        epoch=24,
        selection="Final epoch, fixed before inspecting test results; original gate remains failed",
        size_brotli_q11={k: len(brotli.compress(v, quality=11)) for k, v in blobs.items()},
        panels={},
        limitations=[
            "Stress derivatives share parents; not independent observations",
            "Public benchmark competitor overlap unknown; US50 has known exact train overlaps",
            "Coarse score folds locality into street and district into state; exact spans reported separately",
        ],
    )
    (OUT / "frozen-checkpoint.json").write_text(json.dumps(report, indent=2))
    browser = []

    def measure(name, source):
        counts = Counter()
        examples = []
        source = iter(source)
        while values := list(itertools.islice(source, 128)):
            predictions = {key: predict(model, values) for key, model in models.items()}
            predictions["usaddress"] = {
                r["id"]: [
                    dict(label=LABELS[label], raw=token)
                    for token, label in usaddress.parse(r["text"])
                ]
                for r in values
            }
            for row in values:
                counts["rows"] += 1
                gold = projected(row["components"])
                good = {}
                for key, outputs in predictions.items():
                    actual = outputs[row["id"]]
                    good[key] = projected(actual) == gold
                    counts[key + ":fields"] += good[key]
                    if key != "usaddress" and all("start" in p for p in row["components"]):
                        counts[key + ":spans"] += actual == row["components"]
                counts["pilot_wins_release"] += good["pilot"] and not good["release"]
                counts["pilot_losses_release"] += good["release"] and not good["pilot"]
                counts["pilot_wins_usaddress"] += good["pilot"] and not good["usaddress"]
                counts["pilot_losses_usaddress"] += good["usaddress"] and not good["pilot"]
                counts["quantization_newly_wrong"] += good["float32"] and not good["pilot"]
                counts["quantization_newly_correct"] += good["pilot"] and not good["float32"]
                if not good["pilot"] and len(examples) < 15:
                    examples.append(
                        dict(
                            text=row["text"],
                            gold=row["components"],
                            pilot=predictions["pilot"][row["id"]],
                            release=predictions["release"][row["id"]],
                            usaddress=predictions["usaddress"][row["id"]],
                        )
                    )
                if name != "full-source-test" and counts["rows"] <= 64:
                    browser.append(
                        dict(
                            text=row["text"],
                            panel=name,
                            pilot=predictions["pilot"][row["id"]],
                            release=predictions["release"][row["id"]],
                        )
                    )
            if counts["rows"] % 12800 == 0:
                print(json.dumps(dict(panel=name, progress=counts["rows"])), flush=True)
        summary: dict[str, Any] = dict(counts)
        summary["percent"] = {
            k: round(v / counts["rows"] * 100, 3) for k, v in counts.items() if ":" in k
        }
        report["panels"][name] = summary
        (OUT / f"{name}-failures.json").write_text(json.dumps(examples, indent=2))
        (OUT / "report.json").write_text(json.dumps(report, indent=2))
        print(json.dumps(dict(panel=name, **summary)), flush=True)

    for name, filename in ROBUST_PANELS.items():
        measure(name, rows(DATA / filename.replace("dev", "test", 1)))
    measure(
        "challenge",
        (
            r
            for r in rows(ROOT / "packages/training/tests/fixtures/robustness-challenge.jsonl")
            if r["country"] == "us"
        ),
    )
    natural = list(rows(DATA / "natural-diagnostic.jsonl.gz"))
    overlap = set(
        json.loads((DATA / "manifest.json").read_text())["natural_diagnostic"]["overlap_keys"]
    )
    measure("us50", natural)
    measure(
        "us50-no-exact-train-overlap", (r for r in natural if identity(r["text"]) not in overlap)
    )
    public = json.loads((ROOT / "apps/website/public/evaluation-v4/inputs.json").read_text())
    public = [r for r in public if r["country"] == "us" and r["cohort"] == "complete"]
    assert len(public) == 842
    measure("external-nad", public)
    measure(
        "external-geosearch",
        json.loads((ROOT / "data/geosearch-sample-20260916/inputs.json").read_text()),
    )
    parents = random.Random(391).sample(public, 200)

    def variants(mode):
        for row in parents:
            parts = row["components"]
            if mode == "permutations":
                choices = itertools.permutations(parts)
            elif mode == "partial":
                choices = itertools.chain.from_iterable(
                    itertools.combinations(parts, n) for n in (1, 2, 3)
                )
            else:
                choices = [parts] * 4
            for i, choice in enumerate(choices):
                separator = ("\n", " , ", " ; ", "\t")[i % 4] if mode == "formatting" else ", "
                changed = render_parts(row, choice, separator)
                changed["id"] = f"{row['id']}:{mode}:{i}"
                item = encode(changed)
                assert (
                    item is not None
                    and components(item[1], item[2], changed["text"]) == changed["components"]
                )
                yield changed

    for mode in ("permutations", "partial", "formatting"):
        measure("stress-" + mode, variants(mode))
    measure(
        "full-source-test",
        (
            r
            for r in rows(ROOT / "data/robustness-int5-20260917/test-all.jsonl.gz")
            if r["country"] == "us"
        ),
    )
    # Extra input-boundary probes are diagnostic, not addresses with invented gold.
    probes = [
        "",
        "India",
        "123",
        "MA",
        "02110",
        "New York",
        "Suite 4",
        "PO Box 17",
        "APO AE 09012",
        "RR 2 Box 152, Washington, PA 15301",
        "🏠 123 Main St\nBoston MA 02110",
        "123 Main St\r\nBoston\tMA 02110",
        "02110\n123 Main St\nBoston\nMA",
        "Apt 4B, 123 Main St, Boston MA 02110",
        "123 Main St, Boston, MA 02110, United States",
        "hello this is not an address",
    ]
    probe_rows = [dict(id=f"probe-{i}", text=t, components=None) for i, t in enumerate(probes) if t]
    probe_predictions = {key: predict(model, probe_rows) for key, model in models.items()}
    (OUT / "probes.json").write_text(
        json.dumps(
            [
                dict(text=r["text"], **{k: v[r["id"]] for k, v in probe_predictions.items()})
                for r in probe_rows
            ],
            indent=2,
        )
    )
    for row in probe_rows:
        browser.append(
            dict(
                text=row["text"],
                panel="probe",
                pilot=probe_predictions["pilot"][row["id"]],
                release=probe_predictions["release"][row["id"]],
            )
        )
    (OUT / "browser-inputs.json").write_text(json.dumps(browser, ensure_ascii=False))
    for key in ("pilot", "release"):
        (OUT / f"{key}.bin").write_bytes(blobs[key])
    model = models["float32"].cpu()
    fixtures = [
        encode(dict(text=r["text"], components=None), labeled=False, gap_features=True)
        for r in browser[-40:]
    ]
    export_model(model, OUT / "export", fixtures, bits=5)
    print(
        json.dumps(dict(done=True, report=str(OUT / "report.json"), browser_cases=len(browser))),
        flush=True,
    )


if __name__ == "__main__":
    main()
