import json
import random

from training.data import partial_variants, structural_variant
from training.prepare import tagged
from training.tokenizer import components, encode


def test_safe_structural_augmentation():
    row = tagged(
        "en\tus\t12/house_number Main/road Street/road |/FSEP Austin/city |/FSEP TX/state |/FSEP 78701/postcode"
    )
    row.update(id="parent", split="train", source_components=row["components"])
    original = encode(row)
    before = json.dumps(original)
    variants = list(partial_variants(original[3]))
    assert any(r["text"].startswith("Main Street") for r in variants)
    assert any({p["label"] for p in r["components"]} == {"street_address"} for r in variants)
    for mode in ("partial", "reordered", "combined"):
        for seed in range(40):
            changed, actual = structural_variant(original, random.Random(seed), mode)
            repeated, actual2 = structural_variant(original, random.Random(seed), mode)
            assert changed == repeated and actual == actual2
            assert changed[3]["split"] == "train"
            assert changed[3].get("parent_id", changed[3]["id"]) == "parent"
            assert (
                components(changed[1], changed[2], changed[3]["text"]) == changed[3]["components"]
            )
            assert changed[3]["text"] and changed[3]["text"] != "12"
    assert json.dumps(original) == before
    merged = dict(original[3])
    merged.pop("source_components")
    assert all(
        {p["label"] for p in r["components"]} != {"street_address"}
        for r in partial_variants(merged)
    )
    bare = encode(
        dict(
            id="bare",
            country="us",
            text="12",
            components=[dict(label="street_address", raw="12", start=0, end=2)],
        )
    )
    assert structural_variant(bare, random.Random(1), "partial")[0] is bare


def test_unannotated_content_is_not_silently_removed():
    row = dict(
        id="unlabeled",
        country="us",
        text="near Austin TX",
        components=[
            dict(label="city", raw="Austin", start=5, end=11),
            dict(label="state", raw="TX", start=12, end=14),
        ],
    )
    item = encode(row)
    assert structural_variant(item, random.Random(1), "reordered") == (
        item,
        "unannotated-text-fallback",
    )


def test_reordered_gap_features_and_zip_first():
    row = tagged(
        "en\tus\t12/house_number Main/road St/road Suite/unit 4/unit |/FSEP Austin/city |/FSEP TX/state |/FSEP 78701/postcode"
    )
    row.update(id="gaps", source_components=row["components"])
    item = encode(row, gap_features=True)
    texts = []
    for seed in range(100):
        changed, mode = structural_variant(
            item, random.Random(seed), "reordered", gap_features=True
        )
        assert mode == "reordered"
        assert changed == encode(changed[3], gap_features=True)
        assert components(changed[1], changed[2], changed[3]["text"]) == changed[3]["components"]
        texts.append(changed[3]["text"])
    assert any(text.startswith("78701") for text in texts)
    assert any(text.startswith("Suite 4") for text in texts)
    assert any("\n" in text for text in texts)
