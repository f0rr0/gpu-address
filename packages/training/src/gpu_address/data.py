"""Corpus loading and length-sorted tensor batches."""

import gzip
import json
import random

import torch

from .tokenizer import encode


def load(path, labeled=True, gap_features=False, *, limit=0, seed=2026):
    """Sample before retaining encodings; preserve legacy random.sample ordering.

    A bounded run scans twice, retaining only eligible row indices in the first
    pass. This trades a sequential scan for avoiding a full encoded corpus in RAM.
    """
    if limit < 0:
        raise ValueError("limit must be nonnegative")

    def rows():
        with gzip.open(path, "rt", encoding="utf-8") as source:
            yield from map(json.loads, source)

    rejected = 0
    if not limit:
        result = []
        for row in rows():
            item = encode(row, labeled, gap_features)
            if item is None:
                rejected += 1
            else:
                result.append(item)
        return result, rejected
    eligible = []
    for index, row in enumerate(rows()):
        if encode(row, labeled, gap_features) is None:
            rejected += 1
        else:
            eligible.append(index)
    chosen = random.Random(seed).sample(eligible, min(limit, len(eligible)))
    selected = set(chosen)
    retained = {
        i: encode(row, labeled, gap_features) for i, row in enumerate(rows()) if i in selected
    }
    return [retained[i] for i in chosen], rejected


def batch(rows, device):
    rows = sorted(rows, key=lambda row: len(row[0]), reverse=True)
    lengths = torch.tensor([len(row[0]) for row in rows], dtype=torch.long)
    width = max(len(token) for row in rows for token in row[0])
    byte_ids = torch.zeros(len(rows), int(lengths[0]), width, dtype=torch.long)
    tags = torch.zeros(len(rows), int(lengths[0]), dtype=torch.long)
    for b, (words, gold, _, _) in enumerate(rows):
        tags[b, : len(gold)] = torch.tensor(gold)
        for t, word in enumerate(words):
            byte_ids[b, t, : len(word)] = torch.tensor(word)
    return byte_ids.to(device), tags.to(device), lengths, rows
