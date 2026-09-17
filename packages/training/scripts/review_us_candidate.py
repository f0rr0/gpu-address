"""Predeclared pilot gate and final int5 test review; never publish weights."""

import argparse
import json
from pathlib import Path

from training.train import country_macro, robustness_selection


def gate(panels, baseline, *, pilot):
    _, _, eligible, failures = robustness_selection(panels, baseline)
    failures = list(failures)
    for name in ("reordered", "zip-first"):
        old, new = country_macro(baseline[name]), country_macro(panels[name])
        required = old + 0.10 * (1 - old)
        if name == "zip-first":
            required = max(required, 0.80)
        if new + 1e-12 < required:
            failures.append(name)
    for name in ("partial", "combined"):
        old, new = country_macro(baseline[name]), country_macro(panels[name])
        required = old - 0.005 if pilot else (old + 0.10 * (1 - old) if name == "partial" else old)
        if new + 1e-12 < required:
            failures.append(name)
    if not pilot and country_macro(panels["new-us"]) < country_macro(baseline["new-us"]):
        failures.append("new-us-regression")
    return eligible and not failures, failures


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--pilot", action="store_true")
    args = ap.parse_args()
    completion = json.loads((args.run / "completion.json").read_text())
    epoch = completion["best_epoch"]
    if epoch is None:
        report = dict(passed=False, failures=["no-clean-eligible-checkpoint"])
    elif args.pilot:
        panels = json.loads((args.run / f"epoch-{epoch}.json").read_text())["int5"]
        baseline = json.loads((args.data / "baseline-int5.json").read_text())
        passed, failures = gate(panels, baseline, pilot=True)
        report = dict(
            passed=passed,
            failures=failures,
            epoch=epoch,
            panels={k: country_macro(v) for k, v in panels.items()},
            baseline={k: country_macro(v) for k, v in baseline.items()},
        )
    else:
        import brotli
        import torch
        from training.consolidate import rows
        from training.data import load
        from training.evaluate import evaluate
        from training.expand import file_sha256
        from training.export import serialize
        from training.model import Tagger
        from training.tokenizer import encode
        from training.train import ROBUST_PANELS

        checkpoint = torch.load(args.run / "best.pt", map_location="cpu", weights_only=False)
        assert checkpoint["epoch"] == epoch
        model = Tagger(**checkpoint["metadata"]["config"])
        model.load_state_dict(checkpoint["model"])
        blob, deployed, _ = serialize(model, quantized=True, bits=5)
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        deployed.to(device)
        panels = {}
        for name, filename in ROBUST_PANELS.items():
            values, rejected = load(
                args.data / filename.replace("dev", "test", 1), gap_features=True
            )
            panels[name] = evaluate(deployed, values, device, 128, unsupported=rejected)
        baseline = json.loads((args.data / "baseline-test-int5.json").read_text())
        passed, failures = gate(panels, baseline, pilot=False)
        diagnostics = {}
        for name, path in (
            ("natural", args.data / "natural-diagnostic.jsonl.gz"),
            ("challenge", Path("packages/training/tests/fixtures/robustness-challenge.jsonl")),
        ):
            values = [encode(r, gap_features=True) for r in rows(path) if r["country"] == "us"]
            assert all(item is not None for item in values)
            diagnostics[name] = evaluate(deployed, values, device, 128)
            reference = json.loads((args.data / f"baseline-{name}-int5.json").read_text())
            if diagnostics[name]["exact"] < reference["exact"]:
                failures.append(f"{name}-regression")
        size = len(brotli.compress(blob, quality=11))
        if size > 69016 * 1.05:
            failures.append("brotli-size")
        # This is a private candidate artifact, never the public package model.
        (args.run / "candidate-int5.bin").write_bytes(blob)
        report = dict(
            passed=passed and not failures,
            failures=failures,
            epoch=epoch,
            checkpoint_sha256=file_sha256(args.run / "best.pt"),
            panels=panels,
            diagnostics=diagnostics,
            model_bytes_brotli_q11=size,
            browser_qualification="pending",
            published=False,
        )
    path = args.run / ("pilot-gate.json" if args.pilot else "candidate-review.json")
    path.write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k not in {"diagnostics"}}), flush=True)
    if not report["passed"]:
        raise SystemExit("Gate failed; no automatic continuation or publication")


if __name__ == "__main__":
    main()
