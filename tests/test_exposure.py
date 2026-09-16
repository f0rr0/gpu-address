import gzip
import json
import runpy
import sqlite3
import sys
from pathlib import Path


def test_fixed_budget_exposure_preserves_base_and_filters_supplement(tmp_path, monkeypatch):
    script = (
        Path(__file__).resolve().parents[1] / "docs/evidence/build-balanced-exposure-20260915.py"
    )
    module = runpy.run_path(str(script))
    module["selfcheck"]()
    base, output = tmp_path / "base", tmp_path / "mix"
    (base / "consolidated").mkdir(parents=True)
    row = {
        "id": "base",
        "text": "12 Main Road",
        "country": "us",
        "components": [
            {"label": "house_number", "start": 0, "end": 2, "raw": "12"},
            {"label": "road", "start": 3, "end": 12, "raw": "Main Road"},
        ],
    }
    for name in ("train", "dev", "test"):
        with gzip.open(base / f"{name}.jsonl.gz", "wt") as stream:
            stream.write(json.dumps(row) + "\n")
    original = (base / "train.jsonl.gz").read_bytes()
    (base / "coverage.json").write_text(
        json.dumps({"us": {"address_types": {"number-and-road": 1}}})
    )
    (base / "manifest.json").write_text("{}")
    with sqlite3.connect(base / "consolidated/identities.sqlite") as db:
        db.execute("CREATE TABLE identities(model_input TEXT,model_labels TEXT,reason TEXT)")
    supplement = tmp_path / "supplement.jsonl"
    admitted = dict(
        row,
        id="new",
        text="13 Main Road",
        annotation_status="accepted",
        training_admission=False,
        split="staging",
    )
    admitted["components"] = [dict(row["components"][0], raw="13"), row["components"][1]]
    protected = dict(admitted, id="protected", text="14 Main Road")
    protected["components"] = [dict(row["components"][0], raw="14"), row["components"][1]]
    supplement.write_text("".join(json.dumps(r) + "\n" for r in [admitted, admitted, protected]))
    queue = tmp_path / "queue.json"
    queue.write_text(json.dumps({"rows": [{"text": protected["text"], "components": None}]}))
    monkeypatch.setattr(runpy, "run_path", lambda _: {"PROTECTED": []})
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(script),
            "--base",
            str(base),
            "--output",
            str(output),
            "--rows",
            "10",
            "--supplement",
            str(supplement),
            "--protect-queue",
            str(queue),
        ],
    )
    module["main"]()
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["exposure_counts"] == {"us/number-and-road": 10}
    assert manifest["available_unique_pool_counts"] == {"us/number-and-road": 2}
    assert manifest["supplement_counts"]["supplement_internal_model_duplicate"] == 1
    assert manifest["supplement_counts"]["supplement_protected"] == 1
    with gzip.open(output / "train.jsonl.gz", "rt") as stream:
        emitted = list(map(json.loads, stream))
    assert len(emitted) == 10
    assert all(r["training_admission"] and r["split"] == "train" for r in emitted)
    assert not json.loads(supplement.read_text().splitlines()[0])["training_admission"]
    assert (base / "train.jsonl.gz").read_bytes() == original
    assert (output / "dev.jsonl.gz").read_bytes() == (base / "dev.jsonl.gz").read_bytes()
