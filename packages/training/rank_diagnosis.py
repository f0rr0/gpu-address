"""Measure top-k parse availability; an oracle diagnostic, not deployable accuracy."""

import argparse
import hashlib
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch

from .data import batch, load
from .evaluate import field_exact
from .model import Tagger
from .tokenizer import components


def top_paths(emissions, transitions, starts, ends, k):
    labels = len(starts)
    scores = np.full((labels, k), -np.inf)
    scores[:, 0] = starts + emissions[0]
    history = []
    for emission in emissions[1:]:
        candidates = (scores[:, :, None] + transitions[:, None, :]).reshape(-1, labels)
        previous = np.argsort(-candidates, axis=0, kind="stable")[:k].T
        scores = np.take_along_axis(candidates.T, previous, axis=1) + emission[:, None]
        history.append(previous)
    final = (scores + ends[:, None]).ravel()
    paths = []
    for index in np.argsort(-final, kind="stable")[:k]:
        label, rank = divmod(int(index), k)
        path = [label]
        for previous in reversed(history):
            label, rank = divmod(int(previous[label, rank]), k)
            path.append(label)
        paths.append((path[::-1], float(final[index])))
    return paths


def check():
    rng = np.random.default_rng(17)
    emissions, transitions = rng.normal(size=(4, 3)), rng.normal(size=(3, 3))
    starts, ends = rng.normal(size=3), rng.normal(size=3)
    brute = []
    for path in itertools.product(range(3), repeat=4):
        score = starts[path[0]] + ends[path[-1]] + sum(emissions[i, t] for i, t in enumerate(path))
        score += sum(transitions[a, b] for a, b in zip(path, path[1:]))
        brute.append((list(path), float(score)))
    brute.sort(key=lambda p: -p[1])
    for length in (1, 2, 8):
        actual = top_paths(emissions, transitions, starts, ends, length)
        assert [p for p, _ in actual] == [p for p, _ in brute[:length]]
        assert np.allclose([s for _, s in actual], [s for _, s in brute[:length]])


def main(argv=None):
    check()
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--data", type=Path, required=True)
    args = ap.parse_args(argv)
    torch.set_num_threads(3)
    checkpoint = args.run / "best.pt"
    saved = torch.load(checkpoint, map_location="cpu", weights_only=False)
    model = Tagger(**saved["metadata"]["config"])
    model.load_state_dict(saved["model"])
    model.eval()
    public = args.data / "public-benchmark.jsonl.gz"
    data, rejected = load(public, False, model.config["gap_features"])
    transitions = (model.transitions + model.allowed).detach().numpy()
    starts = (model.start + model.start_allowed).detach().numpy()
    ends = model.end.detach().numpy()
    counts, countries, recovered = Counter(), defaultdict(Counter), []
    with torch.no_grad():
        for start in range(0, len(data), 64):
            x, _, lengths, rows = batch(data[start : start + 64], "cpu")
            emissions = model(x, lengths)
            first = model.decode(emissions, lengths)
            for i, (path, (_, _, offsets, row)) in enumerate(zip(first, rows)):
                rank = (
                    1
                    if field_exact(components(path, offsets, row["text"]), row["components"])
                    else None
                )
                if rank is None:
                    paths = top_paths(
                        emissions[i, : len(path)].numpy(), transitions, starts, ends, 8
                    )
                    assert paths[0][0] == path, "Top-1 parity failed"
                    for j, (alternative, _) in enumerate(paths[1:], 2):
                        if field_exact(
                            components(alternative, offsets, row["text"]), row["components"]
                        ):
                            rank = j
                            if len(recovered) < 20:
                                recovered.append(
                                    dict(
                                        id=row["id"],
                                        rank=rank,
                                        country=row["country"],
                                        score_gap=paths[0][1] - paths[j - 1][1],
                                    )
                                )
                            break
                for count in (counts, countries[row["country"]]):
                    count["rows"] += 1
                    for k in (1, 2, 4, 8):
                        count[f"top_{k}"] += rank is not None and rank <= k
            if start % 2048 == 0:
                print(json.dumps(dict(processed=min(start + 64, len(data)), **counts)), flush=True)
    report = dict(
        counts=counts,
        countries=dict(countries),
        recovered_examples=recovered,
        rejected=rejected,
        model_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        data_sha256=hashlib.sha256(public.read_bytes()).hexdigest(),
        scope="Oracle best-of-k label paths under seven-field token-multiset metric; uses gold to choose. "
        "Multiple paths may produce the same field map. Not achievable accuracy or a reranker.",
    )
    (args.run / "rank-diagnosis.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(counts))


if __name__ == "__main__":
    main()
