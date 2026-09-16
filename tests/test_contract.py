import gzip
import json
import random
import subprocess
import tempfile
from pathlib import Path

import pytest
import torch
from gpu_postal.data import load, read_batch, spool
from gpu_postal.export import export_model
from gpu_postal.model import ARCHITECTURE, Tagger
from gpu_postal.tokenizer import encode


@pytest.mark.parametrize("size", [0, 20, 1000])
def test_bounded_selection_matches_legacy(tmp_path, size):
    rows = [dict(text=f"{i} Main Street", components=[]) for i in range(size)]
    rows.insert(3, dict(text="", components=[]))
    source = tmp_path / "rows.jsonl.gz"
    with gzip.open(source, "wt") as stream:
        for row in rows:
            stream.write(json.dumps(row) + "\n")
    full, rejected = load(source)
    for limit in (1, 7, 100):
        actual, count = load(source, limit=limit, seed=19)
        assert actual == random.Random(19).sample(full, min(limit, len(full)))
        assert count == rejected == 1


@pytest.mark.parametrize("gap_features", [False, True])
def test_disk_training_shuffle_matches_full_list(tmp_path, gap_features):
    rows = [
        dict(text=f"{i}\nMain Road", components=[], country=c)
        for c in ("in", "ng")
        for i in range(8)
    ]
    rows.insert(3, dict(text="", components=[]))
    path = tmp_path / "rows.jsonl.gz"
    with gzip.open(path, "wt") as stream:
        for row in rows:
            stream.write(json.dumps(row) + "\n")
    full, rejected = load(path, gap_features=gap_features)
    with tempfile.TemporaryFile() as target:
        offsets, count = spool(path, target, gap_features=gap_features)
        assert offsets.itemsize == 8 and len(offsets) == len(full)
        assert count == rejected == 1
        random.Random(19).shuffle(offsets)
        random.Random(19).shuffle(full)
        assert read_batch(target, offsets[:2], gap_features=gap_features) == full[:2]
        assert read_batch(target, offsets, gap_features=gap_features) == full


def test_python_export_and_npm_contract(tmp_path):
    torch.manual_seed(7)
    torch.set_num_threads(2)
    model = Tagger(architecture=ARCHITECTURE).eval()
    texts = [
        "12 Main Street",
        "🏠 42 Main St\nLondon",
        "東京都千代田区1丁目",
        "a\u0085b\ufeffc",
        "12 Rue de l’Église",
        "12 Rue de l’E\u0301glise",
        "a",
        "a" * 64,
        " ".join(["a"] * 128),
    ]
    fixtures = [encode(dict(text=text, components=None), labeled=False) for text in texts]
    assert export_model(model, tmp_path, fixtures) < 0.1
    root = Path(__file__).resolve().parents[1]
    subprocess.run(
        ["node", str(root / "packages/core/test/parity.mjs"), str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
    )
