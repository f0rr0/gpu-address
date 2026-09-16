"""Compare lower-bit post-training quantization with the frozen int8 release."""

import argparse
import hashlib
import json
from pathlib import Path

import brotli
import torch
from training.data import batch, load
from training.evaluate import field_exact
from training.export import serialize
from training.model import Tagger
from training.tokenizer import components, encode


@torch.inference_mode()
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bits", type=int, choices=range(2, 8), default=6)
    bits = ap.parse_args().bits
    candidate_name = f"int{bits}"
    run = Path("runs/ordered-h128-english-seven-20260916")
    out = run / f"{candidate_name}-probe"
    out.mkdir(exist_ok=True)
    checkpoint_path = run / "best.pt"
    assert hashlib.sha256(checkpoint_path.read_bytes()).hexdigest() == (
        "436dc0a84fca3816a851f28a5eb56d716153acc993748ddc16768e7c6502e7ec"
    )
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    model = Tagger(**checkpoint["metadata"]["config"])
    model.load_state_dict(checkpoint["model"])
    model.eval()
    int8_blob, int8, _ = serialize(model, quantized=True)
    assert hashlib.sha256(int8_blob).hexdigest() == (
        "4ca878842b0eef37037f9ca5fa8f77096b54bb5ff34c42d4c3927d99b7a65624"
    )
    blob, candidate, _ = serialize(model, quantized=True, bits=bits)
    (out / "model.bin").write_bytes(blob)
    (out / "model.bin.br").write_bytes(brotli.compress(blob, quality=11))
    report = {
        "model_brotli_bytes": {
            "int8": len(brotli.compress(int8_blob, quality=11)),
            candidate_name: len(brotli.compress(blob, quality=11)),
        },
        "datasets": {},
    }
    holdout, rejected = load(
        Path("data/english-seven-20260916/test.jsonl.gz"), gap_features=model.config["gap_features"]
    )
    assert not rejected and len(holdout) == 12115
    external = [
        encode(row, False, model.config["gap_features"])
        for row in json.loads(Path("data/geosearch-sample-20260916/inputs.json").read_text())
    ]
    assert len(external) == 1000 and all(row is not None for row in external)
    for name, data in [("holdout", holdout), ("geosearch", external)]:
        scores = dict(rows=len(data), int8=0, changed=0, gains=0, losses=0)
        scores[candidate_name] = 0
        predictions = []
        for start in range(0, len(data), 64):
            x, _, lengths, rows = batch(data[start : start + 64], "cpu")
            before = int8.decode(int8(x, lengths), lengths)
            after = candidate.decode(candidate(x, lengths), lengths)
            for a, b, (_, _, offsets, row) in zip(before, after, rows):
                a = components(a, offsets, row["text"])
                b = components(b, offsets, row["text"])
                exact = field_exact if name == "geosearch" else lambda p, g: p == g
                old, new = exact(a, row["components"]), exact(b, row["components"])
                scores["int8"] += old
                scores[candidate_name] += new
                scores["changed"] += a != b
                scores["gains"] += new and not old
                scores["losses"] += old and not new
                predictions.append({"text": row["text"], "int8": a, candidate_name: b})
        report["datasets"][name] = scores
        (out / f"{name}-predictions.json").write_text(json.dumps(predictions))
        print(name, scores, flush=True)
    (out / "report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
