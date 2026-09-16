"""Inspect the experimental field parser. Status classification is not trained."""

import argparse
import json
from pathlib import Path

import torch

from .data import batch
from .model import Tagger
from .tokenizer import components, encode


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("checkpoint", type=Path)
    ap.add_argument("text")
    args = ap.parse_args(argv)
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    model = Tagger(**checkpoint["metadata"]["config"])
    model.load_state_dict(checkpoint["model"])
    model.eval()
    item = encode(
        dict(text=args.text, components=None),
        labeled=False,
        gap_features=model.config["gap_features"],
    )
    if item is None:
        result = dict(
            status="unsupported",
            components=[],
            reason="empty input or declared tokenizer/input limit exceeded",
        )
    else:
        with torch.no_grad():
            x, _, lengths, _ = batch([item], "cpu")
            path = model.decode(model(x, lengths), lengths)[0]
        result = dict(
            status="unassessed",
            components=components(path, item[2], args.text),
            offsetEncoding="unicode-codepoints",
            note="Experimental field assignments; address presence and ambiguity are not calibrated",
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
