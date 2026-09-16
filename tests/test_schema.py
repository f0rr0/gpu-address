import copy

import pytest
from gpu_postal.schema import FIELDS, LABELS, seven_fields
from gpu_postal.tokenizer import components, encode


def test_seven_projection_preserves_source_and_geographic_roles():
    text = "Flat 2, Tower A, 10th floor, Main Road, Sector 9, Town, County, State"
    labels = ["unit", "house", "level", "road", "suburb", "city", "state_district", "state"]
    spans, position = [], 0
    for raw, label in zip(text.split(", "), labels):
        start = text.index(raw, position)
        position = start + len(raw)
        spans.append(dict(label=label, raw=raw, start=start, end=position))
    row = dict(text=text, components=spans)
    before = copy.deepcopy(row)
    projected = seven_fields(row)
    assert row == before
    assert FIELDS == [
        "street_address",
        "locality",
        "city",
        "district",
        "state",
        "postcode",
        "country",
    ]
    assert len(LABELS) == 15
    assert [(c["label"], c["raw"]) for c in projected["components"]] == [
        ("street_address", "Flat 2, Tower A, 10th floor, Main Road"),
        ("locality", "Sector 9"),
        ("city", "Town"),
        ("district", "County"),
        ("state", "State"),
    ]
    assert seven_fields(projected) == projected
    item = encode(row)
    assert components(item[1], item[2], text) == projected["components"]
    # Do not silently absorb unrelated text between repeated address components.
    separated = dict(
        text="A Phone B",
        components=[
            dict(label="house", raw="A", start=0, end=1),
            dict(label="road", raw="B", start=8, end=9),
        ],
    )
    assert len(seven_fields(separated)["components"]) == 2
    with pytest.raises(ValueError, match="overlapping"):
        seven_fields(dict(text=text, components=[spans[1], spans[0]]))
