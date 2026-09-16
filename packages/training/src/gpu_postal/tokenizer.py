"""Byte encoding and source spans shared with the browser contract."""

import unicodedata

from .schema import LABELS, seven_fields

MAX_BYTES = 64
MAX_TOKENS = 128


def tokens(text):
    """Unicode source offsets; CJK ideographs remain individually segmentable."""
    result, start = [], None
    for i, char in enumerate(text):
        cjk = "\u3400" <= char <= "\u9fff" or "\uf900" <= char <= "\ufaff"
        word = (char.isalnum() or unicodedata.category(char).startswith("M")) and not cjk
        if not word and start is not None:
            result.append((start, i))
            start = None
        if word and start is None:
            start = i
        elif not word and not char.isspace():
            result.append((i, i + 1))
    if start is not None:
        result.append((start, len(text)))
    return result


def encode(row, labeled=True, gap_features=False):
    if labeled:
        row = seven_fields(row)
    offsets = tokens(row["text"])
    if not offsets or len(offsets) > MAX_TOKENS or len(row["text"]) > 512:
        return None
    byte_rows, targets = [], []
    previous_end = 0
    for start, end in offsets:
        raw = row["text"][start:end].encode("utf-8")
        if len(raw) > MAX_BYTES:
            return None
        if gap_features:
            gap = row["text"][previous_end:start]
            raw = (b"\n" if "\n" in gap or "\r" in gap else b" " if gap else b"") + raw
        previous_end = end
        byte_rows.append([byte + 1 for byte in raw])
        label = "O"
        if labeled:
            for span in row["components"]:
                if span["start"] <= start and end <= span["end"]:
                    label = ("B-" if start == span["start"] else "I-") + span["label"]
                    break
                if start < span["end"] and end > span["start"]:
                    raise ValueError("Gold field boundary cuts a tokenizer token")
        targets.append(LABELS.index(label))
    return byte_rows, targets, offsets, row


def components(path, offsets, text):
    result = []
    previous = "O"
    for label_id, (start, end) in zip(path, offsets):
        tag = LABELS[label_id]
        if tag == "O":
            previous = tag
            continue
        field = tag[2:]
        if tag.startswith("I-") and previous in ("B-" + field, "I-" + field):
            result[-1]["end"] = end
            result[-1]["raw"] = text[result[-1]["start"] : end]
        else:
            result.append(dict(label=field, start=start, end=end, raw=text[start:end]))
        previous = tag
    return result
