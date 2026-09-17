import hashlib
import json

import pytest
import torch
import training.train as training
from training.cli import main
from training.data import case_variant
from training.prepare import tagged, write_rows
from training.tokenizer import components, encode


@pytest.mark.parametrize("case_augmentation", [False, True])
def test_training_checkpoint_and_provenance(tmp_path, monkeypatch, case_augmentation):
    handles = []
    temporary_file = training.tempfile.TemporaryFile

    def tracked_file(*args, **kwargs):
        handle = temporary_file(*args, **kwargs)
        handles.append(handle)
        return handle

    monkeypatch.setattr(training.tempfile, "TemporaryFile", tracked_file)
    data = tmp_path / "data"
    data.mkdir()
    row = tagged("en\tgb\t12/house_number Main/road Street/road |/FSEP London/city")
    row.update(id="smoke", country="gb")
    for split in ("train", "dev"):
        write_rows(data / f"{split}.jsonl.gz", [row])
    (data / "manifest.json").write_text(
        '{"purpose":"training smoke test","split_countries":{"train":{"gb":1}}}'
    )
    run = tmp_path / "run"
    args = [
        "train",
        "--data",
        str(data),
        "--run",
        str(run),
        "--epochs",
        "1",
        "--threads",
        "2",
        "--device",
        "cpu",
    ]
    if case_augmentation:
        args.extend(
            [
                "--case-augmentation",
                "--seed",
                "1",
                "--country-balanced-loss",
                "--selection-metric",
                "country_macro_accuracy",
                "--patience",
                "3",
            ]
        )
    main(args)
    assert len(handles) == 1 and handles[0].closed
    checkpoint = torch.load(run / "best.pt", weights_only=False, map_location="cpu")
    assert checkpoint["epoch"] == 1
    assert json.loads((run / "completion.json").read_text())["stop_reason"] == "epoch-budget"
    if case_augmentation:
        assert checkpoint["metadata"]["country_loss_weights"] == {"gb": 1.0}
        assert (
            checkpoint["metric"]
            == json.loads((run / "epoch-1.json").read_text())["country_macro_accuracy"]
        )
    assert (run / "epoch-1.pt").exists()
    assert checkpoint["metadata"]["arguments"]["case_augmentation"] is case_augmentation
    if case_augmentation:
        result = json.loads((run / "epoch-1.json").read_text())
        assert result["case_augmentation_choices"] == {"lower": 1, "byte_limit_fallback": 0}
    assert checkpoint["metadata"]["train_rows"] == 1
    assert checkpoint["metadata"]["training_storage"] == "temporary-jsonl-uint64-offsets"
    for name, digest in checkpoint["metadata"]["data_files"].items():
        assert hashlib.sha256((data / name).read_bytes()).hexdigest() == digest
    assert (
        checkpoint["metadata"]["data_manifest_sha256"]
        == hashlib.sha256((data / "manifest.json").read_bytes()).hexdigest()
    )
    assert "model.py" in checkpoint["metadata"]["code_sha256"]
    for name, digest in checkpoint["metadata"]["code_sha256"].items():
        assert hashlib.sha256((run / "source" / name).read_bytes()).hexdigest() == digest
    main(["predict", str(run / "best.pt"), "12 Main Street"])
    with pytest.raises(ValueError, match="must not be overwritten"):
        main(args)
    assert json.loads((run / "run.json").read_text())["train_rows"] == 1
    write_rows(data / "train.jsonl.gz", [])
    args[args.index(str(run))] = str(tmp_path / "empty-run")
    with pytest.raises(ValueError, match="must contain supported examples"):
        main(args)
    assert len(handles) == 2 and all(handle.closed for handle in handles)


def test_case_features_preserve_unicode_spans_and_limits():
    row = tagged("en\tgb\t12/house_number Straße/road |/FSEP İstanbul/city")
    for gaps in (False, True):
        original = encode(row, gap_features=gaps)
        before = json.dumps(original, ensure_ascii=False)
        assert case_variant(original, "original") is original
        for mode in ("lower", "upper", "title"):
            changed = case_variant(original, mode)
            assert changed[1:] == original[1:]
            assert components(changed[1], changed[2], row["text"]) == original[3]["components"]
            for old, new in zip(original[0], changed[0]):
                text = bytes(b - 1 for b in old).decode()
                assert bytes(b - 1 for b in new).decode() == getattr(text, mode)()
        assert json.dumps(original, ensure_ascii=False) == before
    # Lowercasing expands İ from two to three UTF-8 bytes; retain the entire original.
    large = encode(tagged("en\tgb\t" + "İ" * 32 + "/road"))
    assert large is not None and case_variant(large, "lower") is large
    with pytest.raises(ValueError, match="Unknown case mode"):
        case_variant(original, "invalid")


def test_training_stops_on_validation_plateau(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    row = tagged("en\tgb\t12/house_number Main/road |/FSEP London/city")
    row.update(id="plateau", country="gb")
    for split in ("train", "dev"):
        write_rows(data / f"{split}.jsonl.gz", [row])
    (data / "manifest.json").write_text("{}")
    monkeypatch.setattr(
        training,
        "evaluate",
        lambda *a, **k: {
            "exact_accuracy": 0.5,
            "countries": {"gb": {"exact": 1, "rows": 2}},
        },
    )
    run = tmp_path / "run"
    main(
        [
            "train",
            "--data",
            str(data),
            "--run",
            str(run),
            "--device",
            "cpu",
            "--threads",
            "2",
            "--epochs",
            "10",
            "--patience",
            "2",
            "--lr",
            "0.001",
        ]
    )
    completed = json.loads((run / "completion.json").read_text())
    assert completed["stop_reason"] == "validation-plateau" and completed["epochs"] == 3
    assert torch.load(run / "best.pt", weights_only=False)["epoch"] == 1
    assert json.loads((run / "epoch-3.json").read_text())["learning_rate"] == 0.0005


def test_robustness_selection_uses_country_macros_and_clean_guards():
    def panel(exact, rows=200):
        return {"countries": {"gb": {"exact": exact, "rows": rows}}}

    baseline = {
        "clean": panel(180),
        "old-us": panel(180),
        "new-us": panel(180),
        "partial": panel(100),
        "reordered": panel(100),
        "combined": panel(100),
    }
    candidate = {
        "clean": panel(179),
        "old-us": panel(178),
        "new-us": panel(178),
        "partial": panel(120),
        "reordered": panel(140),
        "combined": panel(160),
    }
    score, clean, eligible, failures = training.robustness_selection(candidate, baseline)
    assert score == pytest.approx(0.7)
    assert clean == 0.895 and eligible and failures == []
    candidate["new-us"] = panel(177)
    assert training.robustness_selection(candidate, baseline)[2:] == (
        False,
        ["new-us-gb-exact"],
    )


def test_locked_robustness_training_writes_int5_panel_provenance(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    countries = ("us", "gb", "au", "nz", "ca", "ie", "za")
    rows = []
    for country in countries:
        row = tagged("en\tgb\t12/house_number Main/road Street/road |/FSEP London/city")
        row.update(id=f"robust-{country}", country=country)
        rows.append(row)
    write_rows(data / "train.jsonl.gz", rows)
    for name, filename in training.ROBUST_PANELS.items():
        write_rows(data / filename, [rows[0]] if name in {"old-us", "new-us"} else rows)
    (data / "manifest.json").write_text(
        json.dumps({"split_countries": {"train": dict.fromkeys(countries, 1)}})
    )
    empty_baseline = {
        name: {
            "countries": {
                country: {"exact": 0, "rows": 1}
                for country in (("us",) if name in {"old-us", "new-us"} else countries)
            }
        }
        for name in training.ROBUST_PANELS
    }
    (data / "baseline-int5.json").write_text(json.dumps(empty_baseline))
    (data / "augmentation-conflicts.json").write_text("[]")
    real_serialize = training.serialize
    quantization_checks = []

    def checked_serialize(model, **kwargs):
        before = {name: value.detach().clone() for name, value in model.state_dict().items()}
        serialized = real_serialize(model, **kwargs)
        quantization_checks.append(
            all(torch.equal(before[name], value) for name, value in model.state_dict().items())
        )
        return serialized

    monkeypatch.setattr(training, "serialize", checked_serialize)
    run = tmp_path / "run"
    main(
        [
            "train",
            "--robustness",
            "--data",
            str(data),
            "--run",
            str(run),
            "--device",
            "cpu",
            "--threads",
            "2",
            "--max-hours",
            "0.000000001",
        ]
    )
    result = json.loads((run / "epoch-1.json").read_text())
    checkpoint = torch.load(run / "best.pt", weights_only=False)
    assert set(result["int5"]) == set(training.ROBUST_PANELS)
    expected_rows = {
        name: (1 if name in {"old-us", "new-us"} else 7) for name in training.ROBUST_PANELS
    }
    assert {name: panel["rows"] for name, panel in result["int5"].items()} == expected_rows
    assert all(
        panel["unsupported"] == 0 and panel["total"] == expected_rows[name]
        for name, panel in result["int5"].items()
    )
    assert result["eligible"] is True
    assert quantization_checks == [True]
    assert "structural_rng" in checkpoint
    assert checkpoint["metadata"]["arguments"]["batch_size"] == 128
    assert checkpoint["metadata"]["baseline_int5_sha256"]
    assert checkpoint["metadata"]["augmentation_conflicts"]["keys"] == 0
    assert set(checkpoint["metadata"]["validation_panels"]) == set(training.ROBUST_PANELS)
    assert json.loads((run / "completion.json").read_text())["stop_reason"] == "time-budget"


def test_locked_robustness_rejects_initialization(tmp_path):
    with pytest.raises(ValueError, match="start from scratch"):
        main(
            [
                "train",
                "--robustness",
                "--data",
                str(tmp_path),
                "--run",
                str(tmp_path / "run"),
                "--init",
                str(tmp_path / "old.pt"),
            ]
        )
