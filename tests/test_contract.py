import gzip
import json
import random
import subprocess
from pathlib import Path

import torch
from gpu_address.data import load
from gpu_address.export import export_model
from gpu_address.model import Tagger
from gpu_address.tokenizer import encode


def test_bounded_selection_matches_legacy(tmp_path):
    rows = [dict(text=f"{i} Main Street", components=[]) for i in range(20)]
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


def test_python_onnx_and_npm_contract(tmp_path):
    torch.manual_seed(7)
    torch.set_num_threads(2)
    model = Tagger(hidden=8, layers=1).eval()
    texts = [
        "12 Main Street",
        "🏠 42 Main St\nLondon",
        "東京都千代田区1丁目",
        "a\u0085b\ufeffc",
        "12 Rue de l’Église",
        "a" * 64,
    ]
    fixtures = [encode(dict(text=text, components=None), labeled=False) for text in texts]
    assert export_model(model, tmp_path, fixtures) < 1e-4
    root = Path(__file__).resolve().parents[1]
    subprocess.run(
        ["node", str(root / "packages/core/test/parity.mjs"), str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
    )
