import hashlib
import json

import pytest
import torch
from gpu_address.cli import main
from gpu_address.prepare import tagged, write_rows


def test_training_checkpoint_and_provenance(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    row = tagged("en\tgb\t12/house_number Main/road Street/road |/FSEP London/city")
    row.update(id="smoke", country="gb")
    for split in ("train", "dev"):
        write_rows(data / f"{split}.jsonl.gz", [row])
    (data / "manifest.json").write_text('{"purpose":"training smoke test"}')
    run = tmp_path / "run"
    args = [
        "train",
        "--data",
        str(data),
        "--run",
        str(run),
        "--epochs",
        "1",
        "--hidden",
        "8",
        "--threads",
        "2",
        "--device",
        "cpu",
    ]
    main(args)
    checkpoint = torch.load(run / "best.pt", weights_only=False, map_location="cpu")
    assert checkpoint["epoch"] == 1
    assert checkpoint["metadata"]["train_rows"] == 1
    assert "model.py" in checkpoint["metadata"]["code_sha256"]
    for name, digest in checkpoint["metadata"]["code_sha256"].items():
        assert hashlib.sha256((run / "source" / name).read_bytes()).hexdigest() == digest
    main(["predict", str(run / "best.pt"), "12 Main Street"])
    with pytest.raises(ValueError, match="must not be overwritten"):
        main(args)
    assert json.loads((run / "run.json").read_text())["train_rows"] == 1
