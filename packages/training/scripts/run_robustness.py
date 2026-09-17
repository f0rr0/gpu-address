"""Run the approved preparation-to-training sequence; stop on any failed stage."""

import argparse
import json
import os
import subprocess
import sys
import sysconfig
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data/us-robustness-int5-20260917"
RUN = ROOT / "runs/ordered-h128-us-robustness-int5-20260917"
PILOT = ROOT / "runs/ordered-h128-us-robustness-pilot-20260917"


def comparison(checkpoint, split, output):
    return [
        "uv",
        "run",
        "--no-project",
        "--python",
        sys.executable,
        "--with",
        "usaddress==0.5.16",
        "python",
        "packages/training/scripts/compare_us_robustness.py",
        "--data",
        str(DATA),
        "--checkpoint",
        str(checkpoint),
        "--split",
        split,
        "--output",
        str(output),
    ]


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    status = DATA / "pipeline-status.json"
    stages = [
        ("tests", [sys.executable, "-m", "pytest", "packages/training/tests", "-q"]),
        (
            "prepare",
            [
                sys.executable,
                "packages/training/scripts/prepare_us_robustness.py",
            ],
        ),
        (
            "panels-baseline",
            [
                sys.executable,
                "packages/training/scripts/prepare_robustness_panels.py",
                "--data",
                str(DATA),
            ],
        ),
        (
            "baseline-comparison",
            comparison(
                ROOT / "runs/ordered-h128-english-seven-20260916/best.pt",
                "dev",
                DATA / "comparison-baseline.json",
            ),
        ),
        (
            "pilot-panels",
            [
                sys.executable,
                "packages/training/scripts/prepare_us_robustness.py",
                "--pilot-panels",
            ],
        ),
        (
            "pilot",
            [
                sys.executable,
                "-m",
                "training",
                "train",
                "--robustness",
                "--gap-features",
                "--data",
                str(DATA / "pilot"),
                "--run",
                str(PILOT),
                "--device",
                "mps",
                "--epochs",
                "24",
                "--max-hours",
                "2",
            ],
        ),
        (
            "pilot-gate",
            [
                sys.executable,
                "packages/training/scripts/review_us_candidate.py",
                "--data",
                str(DATA),
                "--run",
                str(PILOT),
                "--pilot",
            ],
        ),
        (
            "training",
            [
                sys.executable,
                "-m",
                "training",
                "train",
                "--robustness",
                "--gap-features",
                "--data",
                str(DATA),
                "--run",
                str(RUN),
                "--device",
                "mps",
                "--max-hours",
                "10",
            ],
        ),
        (
            "candidate-comparison",
            comparison(RUN / "best.pt", "test", RUN / "comparison-test.json"),
        ),
        (
            "candidate-review",
            [
                sys.executable,
                "packages/training/scripts/review_us_candidate.py",
                "--data",
                str(DATA),
                "--run",
                str(RUN),
            ],
        ),
    ]
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start-at", choices=[name for name, _ in stages], default="tests")
    args = ap.parse_args()
    stages = stages[[name for name, _ in stages].index(args.start_at) :]
    with (DATA / "pipeline.log").open("a", buffering=1) as log:
        for name, command in stages:
            state = dict(
                stage=name,
                status="running",
                started=time.time(),
                command=command,
                runner_pid=os.getpid(),
            )
            status.write_text(json.dumps(state, indent=2))
            log.write(json.dumps(state) + "\n")
            env = dict(
                os.environ,
                PYTHONPATH=os.pathsep.join((str(ROOT / "packages"), sysconfig.get_path("purelib"))),
            )
            result = subprocess.run(
                command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, env=env
            )
            state.update(
                status="completed" if result.returncode == 0 else "failed",
                ended=time.time(),
                returncode=result.returncode,
            )
            status.write_text(json.dumps(state, indent=2))
            log.write(json.dumps(state) + "\n")
            if result.returncode:
                raise SystemExit(result.returncode)
        status.write_text(
            json.dumps(
                dict(stage="qualification-pending", status="training-completed", time=time.time()),
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
