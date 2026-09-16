import gzip
import io
import json
import sqlite3

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import pytest
from training.corpus import LATIN, address_type, audit_file, conflicts, inventory
from training.expand import acquire, file_sha256, gnaf_row, hf_row
from training.tokenizer import components, encode


def test_latin_scope_is_not_ascii_or_english_only():
    inputs = pa.array(
        [
            "12 Nguyễn Huệ",
            "12 Nguyễn Huệ",
            "Łódź",
            "123",
            "12 Main Street",
            "Москва",
            "दिल्ली",
            "東京",
            "حي",
        ]
    )
    flags = pc.call_function(
        "match_substring_regex", [inputs], pc.MatchSubstringOptions(LATIN)
    ).to_pylist()
    assert flags == [True, True, True, True, True, False, False, False, False]


def test_premise_led_address_needs_no_road():
    # Development example, not a model prediction or unseen accuracy measurement.
    text = "1001 B wing, 10th floor, Rustomjee orinana"
    spans = []
    for label, raw in [
        ("unit", "1001 B wing"),
        ("level", "10th floor"),
        ("house", "Rustomjee orinana"),
    ]:
        start = text.index(raw)
        spans.append(dict(label=label, raw=raw, start=start, end=start + len(raw)))
    row = dict(text=text, components=spans)
    assert address_type(row) == "building-unit-floor"
    item = encode(row)
    assert item is not None
    assert components(item[1], item[2], text) == item[3]["components"]


def test_gnaf_preserves_postal_locality_and_distinct_entity():
    record = dict(
        confidence=1,
        alias_principal="P",
        number_first=12,
        number_last=None,
        street_name="MAIN",
        street_type_code="ST",
        street_suffix_type=None,
        postcode=800,
        building_name="EXAMPLE HOUSE",
        flat_type="UNIT",
        flat_number=2,
        level_type=None,
        level_number=None,
        locality_name="DARWIN",
        state_abbreviation="NT",
        address_detail_pid="address-12",
        street_locality_pid="street-1",
    )
    row = gnaf_row(record)
    assert row["source_entity_group"] == "address-12"
    assert row["source_street_group"] == "street-1"
    assert row["omitted_source_fields"] == []
    assert [(s["label"], s["raw"]) for s in row["components"]][-3:] == [
        ("city", "DARWIN"),
        ("state", "NT"),
        ("postcode", "0800"),
    ]
    item = encode(row)
    assert item is not None
    assert components(item[1], item[2], row["text"]) == item[3]["components"]
    partial = gnaf_row(
        dict(
            record,
            number_first=None,
            street_name=None,
            street_type_code=None,
            postcode=None,
            lot_number="7A",
        )
    )
    assert ("house_number", "LOT 7A") in [(s["label"], s["raw"]) for s in partial["components"]]
    assert not any(s["label"] in {"road", "postcode"} for s in partial["components"])
    item = encode(partial)
    assert item is not None
    assert components(item[1], item[2], partial["text"]) == item[3]["components"]
    letters = gnaf_row(
        dict(
            record,
            flat_number=None,
            flat_number_suffix="A",
            level_type="LEVEL",
            level_number_prefix="B",
        )
    )
    assert [(s["label"], s["raw"]) for s in letters["components"]][1:3] == [
        ("unit", "UNIT A"),
        ("level", "LEVEL B"),
    ]
    item = encode(letters)
    assert item is not None
    assert components(item[1], item[2], letters["text"]) == item[3]["components"]
    with pytest.raises(ValueError, match="range-end-designator-without-number"):
        gnaf_row(dict(record, number_last_suffix="B"))


def test_landmark_relations_preserve_repeated_targets():
    from training.expand import render

    row = render(
        [
            ("house", "Bimco House"),
            ("near", "Next to"),
            ("house", "Acme Plaza"),
            ("near", "Opposite"),
            ("house", "Sangam Cinema"),
        ],
        "in",
        "development-fixture",
    )
    item = encode(row)
    assert item is not None
    assert components(item[1], item[2], row["text"]) == item[3]["components"]


def test_gnaf_audit_renders_filters_and_preserves_source_identity(tmp_path):
    base = dict(
        confidence=1,
        alias_principal="P",
        number_first=12,
        number_last=None,
        lot_number=None,
        street_name="MAIN",
        street_type_code="ST",
        street_suffix_type=None,
        postcode=800,
        building_name="EXAMPLE HOUSE",
        flat_type="UNIT",
        flat_number=2,
        level_type=None,
        level_number=None,
        locality_name="DARWIN",
        state_abbreviation="NT",
        address_detail_pid="address-12",
        street_locality_pid="street-1",
    )
    records = [
        base,
        dict(base, address_detail_pid="another-source-entity"),
        dict(
            base,
            number_first=None,
            lot_number="7A",
            street_name=None,
            street_type_code=None,
            address_detail_pid="lot-7",
            street_locality_pid=None,
        ),
        dict(base, building_name="東京"),
        dict(base, alias_principal="A"),
    ]
    path = tmp_path / "gnaf.parquet"
    pq.write_table(pa.Table.from_pylist(records), path)
    source = dict(
        path="au/gnaf-2022.parquet",
        format="gnaf",
        sha256=file_sha256(path),
        bytes=path.stat().st_size,
    )
    output = tmp_path / "audit"
    report = audit_file(path, source, output)
    assert report["country"] == "au" and report["source_format"] == "gnaf"
    assert report["counts"] == {
        "raw_rows": 5,
        "latin_rows": 3,
        "candidate_rows": 3,
        "candidate:building-unit-floor": 3,
        "excluded:non-latin-script": 1,
        "excluded:retired-or-alias": 1,
    }
    with gzip.open(output / "candidates.jsonl.gz", "rt") as stream:
        candidates = [json.loads(line) for line in stream]
    for row, record in zip(candidates, records):
        assert row["source_fields"] == record
        assert row["source_entity_group"] == record["address_detail_pid"]
        assert row["source_street_group"] == record["street_locality_pid"]
        assert row["label_provenance"] == "generated-from-fields"
        assert row["offset_basis"] == "rendered-input"
        assert row["annotation_status"] == "needs-semantic-review"
        encoded = encode(row)
        assert encoded is not None
        assert components(encoded[1], encoded[2], row["text"]) == encoded[3]["components"]
    fields = [(s["label"], s["raw"]) for s in candidates[2]["components"]]
    assert ("house_number", "LOT 7A") in fields and ("city", "DARWIN") in fields
    assert not any(label == "road" for label, _ in fields)
    with sqlite3.connect(output / "identities.sqlite") as db:
        assert db.execute("SELECT COUNT(*) FROM identities").fetchone()[0] == 2
    assert report["identities"]["unique_texts"] == 2
    assert conflicts(output)["rows"] == 0
    assert not any("No physical entity IDs" in s for s in report["limitations"])
    with pytest.raises(ValueError, match="Unsupported audit source format"):
        audit_file(path, dict(source, format="unknown"), tmp_path / "unknown")


def test_full_audit_preserves_text_and_exposes_collisions(tmp_path):
    base = dict(Address="12 Main Street", Tags=["StreetNumber", "StreetName", "StreetName"])
    rows = [base] * 12001 + [
        dict(Address="12-14 Main Street", Tags=base["Tags"]),
        dict(Address="1214 Main Street", Tags=base["Tags"]),
        dict(Address="12 Main Street", Tags=["Province", "StreetName", "StreetName"]),
        dict(Address=" 12\n Nguyễn  Huệ ", Tags=base["Tags"]),
        dict(Address="12\nMain Street", Tags=["Province", "StreetName", "StreetName"]),
        dict(Address="1 Москва", Tags=["StreetNumber", "StreetName"]),
        dict(Address="a" * 65, Tags=["StreetName"]),
        dict(Address="invalid", Tags=["Unknown"]),
    ]
    source = tmp_path / "vn.parquet"
    pq.write_table(pa.Table.from_pylist(rows), source)
    entry = dict(path="vn/chunk-0.parquet", sha256=file_sha256(source), bytes=source.stat().st_size)
    output = tmp_path / "audit"
    report = audit_file(source, entry, output)
    assert report["counts"]["raw_rows"] == len(rows)
    assert report["counts"]["candidate_rows"] == len(rows) - 3
    assert report["counts"]["excluded:non-latin-script"] == 1
    assert report["counts"]["excluded:input-limits-or-empty"] == 1
    assert report["counts"]["excluded:unknown-tag"] == 1
    assert report["identities"]["conflicting_exact_texts"] == 1
    assert report["identities"]["lossy_keys_with_multiple_texts"] >= 2
    assert report["identities"]["conflicting_model_inputs"] >= 1
    review = conflicts(output)
    assert review["conflicting_texts"] == 1
    assert review["rows"] == 12002
    with gzip.open(output / "conflicts.jsonl.gz", "rt") as stream:
        assert {json.loads(line)["text"] for line in stream} == {"12 Main Street"}
    with pytest.raises(FileExistsError):
        conflicts(output)
    row = hf_row(rows[12004], "vn")
    assert row["text"] == rows[12004]["Address"]
    assert row["components"][1]["raw"] == "Nguyễn  Huệ"
    encoded = encode(row)
    assert components(encoded[1], encoded[2], row["text"]) == encoded[3]["components"]
    before = (output / "report.json").read_bytes()
    with pytest.raises(FileExistsError):
        audit_file(source, entry, output)
    assert (output / "report.json").read_bytes() == before


def test_inventory_pages_all_shards_and_records_missing_countries(tmp_path, monkeypatch):
    from training.corpus import COUNTRY_CODES, TREE

    def response(data, link=None):
        class Response(io.BytesIO):
            headers: dict

        stream = Response(json.dumps(data).encode())
        stream.headers = {"Link": link} if link else {}
        return stream

    def fetch(url, timeout):
        if url == COUNTRY_CODES:
            return response(
                {
                    "3166-1": [
                        dict(alpha_2="IN", name="India"),
                        dict(alpha_2="VN", name="Vietnam"),
                    ]
                }
            )
        entry = dict(path="in/chunk-0.parquet", size=5, lfs=dict(oid="a" * 64))
        if "cursor=" not in url:
            return response([entry], f'<{TREE}?cursor=second>; rel="next"')
        return response([dict(entry, path="in/chunk-1.parquet")])

    monkeypatch.setattr("urllib.request.urlopen", fetch)
    report = inventory(tmp_path)
    assert report["available_shards"] == 2
    assert report["countries"]["in"]["counts"] is None
    assert report["countries"]["vn"]["status"] == "no-source"
    catalog = json.loads((tmp_path / "inventory.json").read_text())
    assert len(catalog["countries"]["in"]["files"]) == 2
    with pytest.raises(ValueError, match="Inventory exists"):
        inventory(tmp_path)


def test_acquisition_streams_and_rejects_oversized_source(tmp_path, monkeypatch):
    payload = b"address-data" * 100000

    class Response(io.BytesIO):
        status = 200
        headers = {}

        def read(self, size=-1):
            assert 0 <= size <= 1024**2
            return super().read(size)

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: Response(payload))
    result = acquire(("complete", ("https://example.test/source", len(payload), False)), tmp_path)
    assert result["status"] == "acquired" and result["bytes"] == len(payload)
    assert file_sha256(tmp_path / "complete.raw") == result["sha256"]
    assert acquire(("prefix", ("https://example.test/source", 12, True)), tmp_path)["bytes"] == 12
    assert (
        acquire(("too-large", ("https://example.test/source", 12, False)), tmp_path)["status"]
        == "unavailable"
    )
    assert not (tmp_path / "too-large.raw").exists()
