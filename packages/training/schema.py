"""Stable field ordering: changing it invalidates existing weights."""

from typing import TypedDict

SOURCE_FIELDS = [
    "house",
    "house_number",
    "road",
    "unit",
    "level",
    "staircase",
    "entrance",
    "po_box",
    "postcode",
    "suburb",
    "city_district",
    "city",
    "island",
    "state_district",
    "state",
    "country_region",
    "country",
    "world_region",
    "category",
    "near",
]
FIELDS = ["street_address", "locality", "city", "district", "state", "postcode", "country"]
LABELS = ["O"] + [prefix + field for field in FIELDS for prefix in ("B-", "I-")]
FIELD_MAP = {
    **dict.fromkeys(
        (
            "house",
            "house_number",
            "road",
            "unit",
            "level",
            "staircase",
            "entrance",
            "po_box",
            "near",
        ),
        "street_address",
    ),
    **dict.fromkeys(("suburb", "city_district", "island"), "locality"),
    "state_district": "district",
    "country_region": "state",
    "category": None,
    "world_region": None,
    **{field: field for field in FIELDS},
}


def seven_fields(row):
    """Project source annotations without modifying them or inventing missing text."""
    spans = []
    previous_end = 0
    for source in row["components"]:
        label = FIELD_MAP[source["label"]]
        if "start" not in source:
            raise ValueError("Training projection requires exact source offsets")
        start, end = source["start"], source["end"]
        if (
            not (previous_end <= start < end <= len(row["text"]))
            or row["text"][start:end] != source["raw"]
        ):
            raise ValueError("Invalid or overlapping source spans")
        previous_end = end
        if label is None:
            continue
        gap = row["text"][spans[-1]["end"] : start] if spans else ""
        if spans and spans[-1]["label"] == label and all(c.isspace() or c in ",;" for c in gap):
            spans[-1]["end"] = end
            spans[-1]["raw"] = row["text"][spans[-1]["start"] : end]
        else:
            spans.append(dict(label=label, start=start, end=end, raw=source["raw"]))
    return dict(row, components=spans)


class Component(TypedDict):
    label: str
    start: int
    end: int
    raw: str
