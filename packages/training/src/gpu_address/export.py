"""Export float ONNX and stored-int8 weights; evaluate quantization and runtime parity."""

import argparse
import json
import random
from pathlib import Path

import brotli
import numpy as np
import onnxruntime as ort
import torch

from .data import batch, load
from .evaluate import evaluate
from .model import Tagger
from .paths import ROOT
from .schema import LABELS
from .teacher import field_map
from .tokenizer import components, encode


def export_model(model, folder, fixtures):
    x, _, lengths, _ = batch([fixtures[0]], "cpu")
    with torch.no_grad():
        torch.onnx.export(
            model,
            (x, lengths),
            str(folder / "model.onnx"),
            input_names=["byte_ids", "lengths"],
            output_names=["emissions"],
            dynamic_axes={
                "byte_ids": {0: "batch", 1: "tokens", 2: "bytes"},
                "lengths": {0: "batch"},
                "emissions": {0: "batch", 1: "tokens"},
            },
            opset_version=17,
            dynamo=False,
        )
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    session = ort.InferenceSession(
        str(folder / "model.onnx"), sess_options=options, providers=["CPUExecutionProvider"]
    )
    saved = []
    max_error = 0
    with torch.no_grad():
        for fixture in fixtures:
            x, _, lengths, rows = batch([fixture], "cpu")
            reference = model(x, lengths)
            actual = session.run(None, {"byte_ids": x.numpy(), "lengths": lengths.numpy()})[0]
            error = float(np.max(np.abs(reference.numpy() - actual)))
            max_error = max(max_error, error)
            assert error < 1e-4, error
            path = model.decode(reference, lengths)[0]
            assert model.decode(torch.from_numpy(actual), lengths)[0] == path
            saved.append(
                dict(
                    text=fixture[3]["text"],
                    byte_ids=x.tolist(),
                    lengths=lengths.tolist(),
                    emissions=reference.tolist(),
                    path=path,
                    components=components(path, fixture[2], fixture[3]["text"]),
                )
            )
        # Exercise dynamic batch sizes and unequal lengths, not only the export example.
        x, _, lengths, _ = batch(fixtures[:3], "cpu")
        reference = model(x, lengths)
        actual = session.run(None, {"byte_ids": x.numpy(), "lengths": lengths.numpy()})[0]
        assert np.max(np.abs(reference.numpy() - actual)) < 1e-4
        assert model.decode(reference, lengths) == model.decode(torch.from_numpy(actual), lengths)
    (folder / "fixtures.json").write_text(json.dumps(saved, ensure_ascii=False))
    decoder = {
        name: getattr(model, name).detach().tolist()
        for name in ["transitions", "start", "end", "allowed", "start_allowed"]
    }
    decoder["labels"] = LABELS
    decoder["gap_features"] = model.config["gap_features"]
    (folder / "decoder.json").write_text(json.dumps(decoder))
    return max_error


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--data", type=Path, default=ROOT / "data/expanded")
    ap.add_argument("--dev-limit", type=int, default=6000)
    args = ap.parse_args(argv)
    torch.set_num_threads(4)
    checkpoint = torch.load(args.run / "best.pt", map_location="cpu", weights_only=False)
    model = Tagger(**checkpoint["metadata"]["config"])
    model.load_state_dict(checkpoint["model"])
    model.eval()
    folder = args.run / "export"
    folder.mkdir(exist_ok=True)
    dev, rejected = load(
        args.data / "dev.jsonl.gz",
        gap_features=model.config["gap_features"],
        limit=args.dev_limit,
        seed=71,
    )
    fixture_texts = [
        "Flat 4, 12 Example Road, London SW1A 1AA",
        "東京都千代田区丸の内1丁目",
        "12 Rue de l’Église, Montréal H2X 1Y4",
        "🏠 42 Main Street\nLondon",
        "123 Main St",
        "Paris",
        "12\r\nMain Street",
        "12\tMain Street",
        " " + "a" * 64,
    ]
    fixtures = [
        encode(dict(text=text, components=None), False, model.config["gap_features"])
        for text in fixture_texts
    ]
    fixtures += random.Random(19).sample(dev, min(20, len(dev)))
    max_error = export_model(model, folder, fixtures)
    # Quantize storage, then dequantize for inference. This measures weight-storage
    # savings, not integer arithmetic speed or the complete browser package.
    stored, quantized_state = {}, {}
    for name, tensor in model.state_dict().items():
        values = tensor.detach().numpy()
        if tensor.ndim >= 2 and name not in ["allowed", "transitions"]:
            axes = tuple(range(1, values.ndim))
            scale = np.maximum(np.abs(values).max(axis=axes, keepdims=True) / 127, 1e-12).astype(
                "float32"
            )
            packed = np.clip(np.round(values / scale), -127, 127).astype("int8")
            stored[name] = packed
            stored[name + ".scale"] = scale
            quantized_state[name] = torch.from_numpy(packed.astype("float32") * scale)
        else:
            stored[name] = values
            quantized_state[name] = tensor
    np.savez_compressed(folder / "weights-int8.npz", **stored)
    quantized = Tagger(**model.config)
    quantized.load_state_dict(quantized_state)
    quantized.eval()
    torch.save(
        dict(model=quantized_state, metadata=checkpoint["metadata"]), folder / "dequantized.pt"
    )
    float_result = evaluate(model, dev, "cpu")
    quantized_result = evaluate(quantized, dev, "cpu")
    flips = dict(changed_outputs=0, newly_wrong=0, newly_correct=0)
    with torch.no_grad():
        for start in range(0, len(dev), 64):
            x, _, lengths, rows = batch(dev[start : start + 64], "cpu")
            before = model.decode(model(x, lengths), lengths)
            after = quantized.decode(quantized(x, lengths), lengths)
            for first, second, (_, _, offsets, row) in zip(before, after, rows):
                a = components(first, offsets, row["text"])
                b = components(second, offsets, row["text"])
                flips["changed_outputs"] += a != b
                flips["newly_wrong"] += a == row["components"] and b != row["components"]
                flips["newly_correct"] += a != row["components"] and b == row["components"]
    public, rejected_public = load(
        args.data / "public-benchmark.jsonl.gz",
        labeled=False,
        gap_features=model.config["gap_features"],
    )
    count, correct = 0, 0
    countries = {}
    with torch.no_grad():
        for start in range(0, len(public), 64):
            x, _, lengths, rows = batch(public[start : start + 64], "cpu")
            paths = model.decode(model(x, lengths), lengths)
            for path, (_, _, offsets, row) in zip(paths, rows):
                predicted = components(path, offsets, row["text"])
                exact = field_map(predicted) == field_map(row["components"])
                correct += exact
                count += 1
                countries.setdefault(row["country"], dict(rows=0, exact=0))
                countries[row["country"]]["rows"] += 1
                countries[row["country"]]["exact"] += exact
    raw_onnx = (folder / "model.onnx").read_bytes()
    compressed = brotli.compress(raw_onnx)
    (folder / "model.onnx.br").write_bytes(compressed)
    report = dict(
        checkpoint_epoch=checkpoint["epoch"],
        parameters=sum(p.numel() for p in model.parameters()),
        dev_rows=len(dev),
        dev_rejected=rejected,
        float_exact=float_result["exact_accuracy"],
        int8_storage_exact=quantized_result["exact_accuracy"],
        quantization_flips=flips,
        onnx_max_abs_error=max_error,
        onnx_fixture_paths_equal=True,
        public_benchmark=dict(
            rows=count,
            rejected=rejected_public,
            exact=correct,
            accuracy=correct / (count + rejected_public),
            countries=countries,
            metric="normalized field-map agreement; rejected cases count as incorrect",
        ),
        bytes=dict(
            float_onnx=len(raw_onnx),
            float_onnx_brotli=len(compressed),
            stored_int8_npz=(folder / "weights-int8.npz").stat().st_size,
        ),
        limitations=[
            "Stored-int8 bytes exclude runtime, tokenizer and decoder",
            "Public benchmark is not independently collected gold",
            "No input-status/abstention accuracy claim",
        ],
    )
    (folder / "report.json").write_text(json.dumps(report, indent=2))
    (folder / "float-dev.json").write_text(json.dumps(float_result, indent=2, ensure_ascii=False))
    (folder / "int8-dev.json").write_text(
        json.dumps(quantized_result, indent=2, ensure_ascii=False)
    )
    print(
        json.dumps({k: v for k, v in report.items() if k != "public_benchmark"}, indent=2),
        flush=True,
    )
    print("Public benchmark:", correct, "/", count + rejected_public, flush=True)


if __name__ == "__main__":
    main()
