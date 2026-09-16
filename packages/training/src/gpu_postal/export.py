"""Export float32 qualification and int8 candidate WebGPU models."""

import argparse
import json
import random
import struct
from pathlib import Path

import brotli
import torch

from .data import batch, load
from .evaluate import evaluate, field_exact
from .model import ARCHITECTURE, Tagger
from .paths import ROOT
from .tokenizer import components, encode

WEIGHTS = (
    "embedding.weight",
    "char_conv.weight",
    "char_conv.bias",
    "project.weight",
    "project.bias",
    "local",
    "local_bias",
    "layers.0.gate.weight",
    "layers.0.gate.bias",
    "layers.0.candidate.weight",
    "layers.0.candidate.bias",
    "layers.0.combine.weight",
    "layers.0.combine.bias",
    "layers.1.gate.weight",
    "layers.1.gate.bias",
    "layers.1.candidate.weight",
    "layers.1.candidate.bias",
    "layers.1.combine.weight",
    "layers.1.combine.bias",
    "output.weight",
    "output.bias",
    "transitions",
    "start",
    "end",
)


def serialize(model: Tagger, *, quantized: bool) -> tuple[bytes, Tagger, float]:
    parameters = dict(model.named_parameters())
    if (
        model.config.get("architecture") != ARCHITECTURE
        or set(parameters) != set(WEIGHTS)
        or sum(value.numel() for value in parameters.values()) != 154446
    ):
        raise ValueError("Model tensor layout changed; update the WebGPU runtime")
    if any(not torch.isfinite(value).all() for value in parameters.values()):
        raise ValueError("Non-finite model parameters")
    header = struct.pack(
        "<4sIIII", b"GPA3", 1, int(quantized), len(WEIGHTS), int(model.config["gap_features"])
    )
    if not quantized:
        payload = b"".join(
            parameters[name].detach().cpu().float().contiguous().numpy().astype("<f4").tobytes()
            for name in WEIGHTS
        )
        return header + payload, model, 0.0
    scales, codes, state = [], [], model.state_dict()
    max_error = 0.0
    for name in WEIGHTS:
        value = parameters[name].detach().cpu()
        scale = max(float(value.abs().max()) / 127, 1e-12)
        code = (value / scale).round().clamp(-127, 127).to(torch.int8)
        restored = code.float() * scale
        max_error = max(max_error, float((value - restored).abs().max()))
        scales.append(scale)
        codes.append(code.contiguous().numpy().tobytes())
        state[name] = restored
    deployed = Tagger(**model.config)
    deployed.load_state_dict(state)
    deployed.eval()
    return header + struct.pack(f"<{len(scales)}f", *scales) + b"".join(codes), deployed, max_error


def export_model(model: Tagger, folder: Path, fixtures) -> float:
    folder.mkdir(parents=True, exist_ok=True)
    for suffix, quantized in [(".f32", False), ("", True)]:
        blob, deployed, max_error = serialize(model, quantized=quantized)
        (folder / f"model{suffix}.bin").write_bytes(blob)
        saved = []
        with torch.no_grad():
            for fixture in fixtures:
                x, _, lengths, _ = batch([fixture], "cpu")
                emissions = deployed(x, lengths)
                path = deployed.decode(emissions, lengths)[0]
                saved.append(
                    dict(
                        text=fixture[3]["text"],
                        byte_ids=x.tolist(),
                        emissions=emissions.tolist(),
                        path=path,
                        components=components(path, fixture[2], fixture[3]["text"]),
                    )
                )
        (folder / f"fixtures{suffix}.json").write_text(json.dumps(saved, ensure_ascii=False))
    return max_error


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--data", type=Path, default=ROOT / "data/expanded")
    ap.add_argument("--dev-limit", type=int, default=6000)
    args = ap.parse_args(argv)
    checkpoint = torch.load(args.run / "best.pt", map_location="cpu", weights_only=False)
    model = Tagger(**checkpoint["metadata"]["config"])
    model.load_state_dict(checkpoint["model"])
    model.eval()
    folder = args.run / "export"
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
    _, deployed, _ = serialize(model, quantized=True)
    unsupported_dev = None if args.dev_limit else rejected
    float_result = evaluate(model, dev, "cpu", unsupported=unsupported_dev)
    deployed_result = evaluate(deployed, dev, "cpu", unsupported=unsupported_dev)
    flips = dict(changed_outputs=0, newly_wrong=0, newly_correct=0)
    with torch.no_grad():
        for start in range(0, len(dev), 64):
            x, _, lengths, rows = batch(dev[start : start + 64], "cpu")
            before = model.decode(model(x, lengths), lengths)
            after = deployed.decode(deployed(x, lengths), lengths)
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
            paths = deployed.decode(deployed(x, lengths), lengths)
            for path, (_, _, offsets, row) in zip(paths, rows):
                predicted = components(path, offsets, row["text"])
                exact = field_exact(predicted, row["components"])
                correct += exact
                count += 1
                countries.setdefault(row["country"], dict(rows=0, exact=0))
                countries[row["country"]]["rows"] += 1
                countries[row["country"]]["exact"] += exact
    raw = (folder / "model.bin").read_bytes()
    compressed = brotli.compress(raw)
    (folder / "model.bin.br").write_bytes(compressed)
    report = dict(
        format="GPA3 ordered-byte-conv32-scan128-v3-seven int8; float32 qualification sibling",
        checkpoint_epoch=checkpoint["epoch"],
        parameters=sum(p.numel() for p in model.parameters()),
        dev_rows=len(dev),
        dev_rejected=rejected,
        float_exact=float_result["exact_accuracy"],
        deployed_int8_exact=deployed_result["exact_accuracy"],
        quantization_flips=flips,
        max_parameter_error=max_error,
        public_benchmark=dict(
            rows=count,
            rejected=rejected_public,
            exact=correct,
            accuracy=correct / (count + rejected_public),
            countries=countries,
            metric="exact seven-field token multisets; order/commas/case/whitespace ignored; rejected cases count as incorrect",
        ),
        bytes=dict(model=len(raw), model_brotli=len(compressed)),
        limitations=[
            "Public benchmark is not independently collected gold",
            "No input-status/abstention accuracy claim",
            "Browser latency and compatibility require a real-browser run",
        ],
    )
    (folder / "report.json").write_text(json.dumps(report, indent=2))
    (folder / "float-dev.json").write_text(json.dumps(float_result, indent=2, ensure_ascii=False))
    (folder / "int8-dev.json").write_text(json.dumps(deployed_result, indent=2, ensure_ascii=False))
    print(
        json.dumps({k: v for k, v in report.items() if k != "public_benchmark"}, indent=2),
        flush=True,
    )
    print("Public benchmark:", correct, "/", count + rejected_public, flush=True)


if __name__ == "__main__":
    main()
