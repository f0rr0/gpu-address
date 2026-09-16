"""Corpus loading and length-sorted tensor batches."""

import gzip
import json
import random
from array import array

import torch

from .tokenizer import MAX_BYTES, encode


def case_variant(item, mode):
    """Training-only byte features; labels and original source offsets stay intact."""
    if mode not in ("original", "lower", "upper", "title"):
        raise ValueError(f"Unknown case mode: {mode}")
    if mode == "original":
        return item
    words, gold, offsets, row = item
    changed = []
    for word in words:
        text = bytes(b - 1 for b in word).decode("utf-8")
        raw = getattr(text, mode)().encode("utf-8")
        # Preserve the original example if Unicode case expansion exceeds the byte limit.
        # A gap-feature prefix is not part of the tokenizer's 64-byte word limit.
        if len(raw.lstrip(b" \n")) > MAX_BYTES:
            return item
        changed.append([b + 1 for b in raw])
    return changed, gold, offsets, row


def load(path, labeled=True, gap_features=False, *, limit=0, seed=2026):
    """Sample before retaining encodings; preserve legacy random.sample ordering.

    A bounded run counts eligible rows, then retains only sampled encodings on
    its second scan. Selection memory is proportional to the requested limit.
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
    eligible = 0
    for row in rows():
        if encode(row, labeled, gap_features) is None:
            rejected += 1
        else:
            eligible += 1
    chosen = random.Random(seed).sample(range(eligible), min(limit, eligible))
    selected = set(chosen)
    retained = {}
    index = 0
    for row in rows():
        item = encode(row, labeled, gap_features)
        if item is not None:
            if index in selected:
                retained[index] = item
            index += 1
    return [retained[i] for i in chosen], rejected


def spool(path, target, gap_features=False):
    """Index eligible raw rows on disk; retain eight bytes per row in memory."""
    offsets, rejected = array("Q"), 0
    with gzip.open(path, "rb") as source:
        for line in source:
            if encode(json.loads(line), gap_features=gap_features) is None:
                rejected += 1
            else:
                offsets.append(target.tell())
                target.write(line)
    target.flush()
    return offsets, rejected


def read_batch(source, offsets, gap_features=False):
    result = []
    for offset in offsets:
        source.seek(offset)
        item = encode(json.loads(source.readline()), gap_features=gap_features)
        if item is None:
            raise ValueError("Previously admitted training row no longer encodes")
        result.append(item)
    return result


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
