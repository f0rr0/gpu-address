"""One full training run, then frozen evaluation and export; never auto-publish."""

import json
import subprocess
import sys
from pathlib import Path

import torch
from gpu_postal.cli import main
from gpu_postal.data import load
from gpu_postal.evaluate import evaluate
from gpu_postal.expand import file_sha256
from gpu_postal.export import serialize
from gpu_postal.model import Tagger

DATA = Path("data/english-seven-20260916")
RUN = Path("runs/ordered-h128-english-seven-20260916")


def run():
    manifest = json.loads((DATA / "manifest.json").read_text())
    assert manifest["status"] == "ready"
    for name, sha in manifest["outputs"].items():
        if file_sha256(DATA / name) != sha:
            raise ValueError(f"Prepared data changed: {name}")
    main(
        [
            "train",
            "--data",
            str(DATA),
            "--run",
            str(RUN),
            "--device",
            "mps",
            "--batch-size",
            "128",
            "--epochs",
            "12",
            "--lr",
            "0.001",
            "--seed",
            "2026",
            "--case-augmentation",
            "--country-balanced-loss",
            "--selection-metric",
            "country_macro_accuracy",
            "--patience",
            "3",
        ]
    )
    torch.set_num_threads(2)
    checkpoint = torch.load(RUN / "best.pt", map_location="cpu", weights_only=False)
    model = Tagger(**checkpoint["metadata"]["config"])
    model.load_state_dict(checkpoint["model"])
    model.eval()
    heldout, rejected = load(DATA / "test.jsonl.gz")
    _, deployed, _ = serialize(model, quantized=True)
    report = dict(
        checkpoint_sha256=file_sha256(RUN / "best.pt"),
        test_sha256=file_sha256(DATA / "test.jsonl.gz"),
        epoch=checkpoint["epoch"],
        scope="Frozen same-source street-group holdout, not representative country-wide accuracy",
        float32=evaluate(model, heldout, "cpu", unsupported=rejected),
        int8=evaluate(deployed, heldout, "cpu", unsupported=rejected),
    )
    (RUN / "heldout-test.json").write_text(json.dumps(report, indent=2))
    main(["export", "--run", str(RUN), "--data", str(DATA), "--dev-limit", "0"])
    subprocess.run(
        [
            sys.executable,
            "docs/evidence/evaluate-seven-20260916.py",
            str(RUN / "best.pt"),
            "--output",
            str(RUN / "protected-diagnostics"),
        ],
        check=True,
    )
    subprocess.run(["npm", "run", "build"], check=True)
    subprocess.run(["npm", "run", "test:parity", "--", str(RUN / "export")], check=True)
    (RUN / "qualification-status.json").write_text(
        json.dumps(
            dict(
                status="offline-checks-complete",
                checkpoint_sha256=file_sha256(RUN / "best.pt"),
                remaining=[
                    "Review country tradeoffs against previous candidates",
                    "Actual browser WebGPU parity",
                    "Resolve weight redistribution terms without assigning an unapproved license",
                    "Publish selected research artifact",
                ],
            ),
            indent=2,
        )
    )
    print(
        "Offline qualification complete; publication and browser qualification remain pending",
        flush=True,
    )


if __name__ == "__main__":
    try:
        run()
    except Exception as error:
        if RUN.exists():
            (RUN / "pipeline-error.json").write_text(json.dumps(dict(error=repr(error))))
        raise
