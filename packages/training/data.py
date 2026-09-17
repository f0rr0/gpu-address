"""Corpus loading and length-sorted tensor batches."""

import gzip
import hashlib
import json
import random
import unicodedata
from array import array

import torch

from .schema import FIELD_MAP, seven_fields
from .tokenizer import MAX_BYTES, components, encode


def ambiguity_key(row):
    values = sorted(
        "".join(c for c in unicodedata.normalize("NFKC", p["raw"]).casefold() if c.isalnum())
        for p in row["components"]
    )
    return hashlib.sha256(json.dumps(values).encode()).hexdigest()


def render_parts(row, parts, separator=" "):
    """Move annotated spans together; never infer new field boundaries."""
    text, spans = "", []
    for part in parts:
        if text:
            text += separator
        start = len(text)
        text += part["raw"]
        spans.append(dict(label=part["label"], raw=part["raw"], start=start, end=len(text)))
    result = dict(row, text=text, components=spans, parent_id=row.get("parent_id", row["id"]))
    result.pop("source_components", None)
    return seven_fields(result)


def partial_variants(row):
    """Enumerate only the locked, safe field/subfield omissions."""
    parts = row["components"]
    labels = {p["label"] for p in parts}
    fine = row.get("source_components", [])
    road = any(p["label"] in {"road", "po_box"} for p in fine)
    choices = []
    for label in ("country", "postcode", "state", "district", "locality"):
        if label in labels:
            choices.append([p for p in parts if p["label"] != label])
    for keep in (
        {"street_address"},
        {"street_address", "city"},
        {"city", "state"},
        {"city", "postcode"},
    ):
        if keep < labels and (keep != {"street_address"} or road):
            choices.append([p for p in parts if p["label"] in keep])
    if fine and any(p["label"] == "road" for p in fine):
        for drop in ({"unit", "level"}, {"house"}, {"house_number"}):
            if any(p["label"] in drop for p in fine):
                choices.append([p for p in fine if p["label"] not in drop])
    seen = set()
    for selected in choices:
        remaining = {FIELD_MAP[p["label"]] for p in selected} - {None}
        if not remaining or (
            "street_address" not in remaining and len(remaining - {"country"}) < 2
        ):
            continue
        # A merged-only street span cannot establish that a bare-number reduction is safe.
        if remaining == {"street_address"} and not road:
            continue
        candidate = render_parts(row, selected)
        key = tuple((p["label"], p["raw"]) for p in candidate["components"])
        if key not in seen:
            seen.add(key)
            yield candidate


def structural_variant(item, rng, mode=None, *, blocked=frozenset(), gap_features=False):
    """Online 50/25/15/10 original/partial/reordered/combined augmentation."""
    if mode is None:
        draw = rng.random()
        mode = (
            "original"
            if draw < 0.5
            else "partial"
            if draw < 0.75
            else ("reordered" if draw < 0.9 else "combined")
        )
    if mode not in {"original", "partial", "reordered", "combined"}:
        raise ValueError("Unknown structural augmentation mode")
    if mode == "original":
        return item, "original"
    row = item[3]
    # Unannotated words must not disappear during span re-rendering.
    cursor = 0
    for part in row["components"]:
        if any(c.isalnum() for c in row["text"][cursor : part["start"]]):
            return item, "unannotated-text-fallback"
        cursor = part["end"]
    if any(c.isalnum() for c in row["text"][cursor:]):
        return item, "unannotated-text-fallback"
    if mode in {"partial", "combined"}:
        choices = [r for r in partial_variants(row) if ambiguity_key(r) not in blocked]
        if not choices:
            return item, "no-partial-fallback"
        row = rng.choice(choices)
    parts = row["components"]
    if mode in {"reordered", "combined"}:
        # Multiple separated street spans may belong together: do not guess a partition.
        labels = [p["label"] for p in parts]
        if len(labels) != len(set(labels)) or len(parts) < 2:
            return item, "unsafe-reorder-fallback"
        orders = []
        street_last = [p for p in parts if p["label"] != "street_address"] + [
            p for p in parts if p["label"] == "street_address"
        ]
        zip_first = [p for p in parts if p["label"] == "postcode"] + [
            p for p in parts if p["label"] != "postcode"
        ]
        reverse = iter(reversed([p for p in parts if p["label"] != "street_address"]))
        reversed_admin = [p if p["label"] == "street_address" else next(reverse) for p in parts]
        shuffled = rng.sample(parts, len(parts))
        if shuffled == parts:
            shuffled = parts[1:] + parts[:1]
        for order in (street_last, zip_first, reversed_admin, shuffled):
            if order != parts and order not in orders:
                orders.append(order)
        # Only move units when the source gives a complete fine-grained partition.
        fine = row.get("source_components", [])
        if fine and seven_fields(dict(row, components=fine))["components"] == parts:
            units = [p for p in fine if p["label"] in {"unit", "level"}]
            if units:
                unit_first = units + [p for p in fine if p not in units]
                if unit_first != fine:
                    orders.append(unit_first)
        if not orders:
            return item, "no-reorder-fallback"
        parts = rng.choice(orders)
    changed = render_parts(row, parts, rng.choice((" ", ", ", "\n")))
    encoded = encode(changed, gap_features=gap_features)
    if (
        encoded is None
        or components(encoded[1], encoded[2], changed["text"]) != encoded[3]["components"]
    ):
        return item, "encoding-fallback"
    return encoded, mode


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
