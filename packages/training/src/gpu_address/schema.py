"""Stable field ordering: changing it invalidates existing weights."""

from typing import TypedDict

FIELDS = [
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
LABELS = ["O"] + [prefix + field for field in FIELDS for prefix in ("B-", "I-")]


class Component(TypedDict):
    label: str
    start: int
    end: int
    raw: str
