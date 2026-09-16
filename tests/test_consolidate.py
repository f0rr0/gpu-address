import gzip
import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from gpu_postal.consolidate import consolidate, rows
from gpu_postal.corpus import audit_file
from gpu_postal.expand import file_sha256, hf_row


def test_global_conflicts_exact_dedup_and_protected_streets(tmp_path):
    tags = ["StreetNumber", "StreetName", "StreetName", "Municipality"]

    def record(text, labels=tags):
        return dict(Address=text, Tags=labels)

    first = [
        record("12-14 Main St Town"),
        record("1214 Main St Town"),
        record("22 Other St Town"),
        record("33 Shared St Town"),
        record("91 Protected Road Town"),
        record("95 Protected Road Other 12345", [*tags, "PostalCode"]),
        record("77 Renamed Road Elsewhere"),
    ]
    second = [
        first[0],
        record("33 Shared St Town", ["Province", *tags[1:]]),
        record("22\nOther St Town", ["Province", *tags[1:]]),
        first[-2],
        record("77\nRenamed Road Elsewhere"),
    ]
    catalog = dict(countries={})
    for country, records in [
        ("in", first),
        ("vn", second),
        ("xx", [dict(Address="Москва", Tags=["Municipality"])]),
    ]:
        source = tmp_path / (country + ".parquet")
        pq.write_table(pa.Table.from_pylist(records), source)
        entry = dict(
            path=country + "/chunk-0.parquet",
            bytes=source.stat().st_size,
            sha256=file_sha256(source),
        )
        catalog["countries"][country] = dict(files=[entry])
        audit_file(source, entry, tmp_path / "audit" / (country + "-chunk-0.parquet"))
    (tmp_path / "inventory.json").write_text(json.dumps(catalog))
    candidate = tmp_path / "audit/in-chunk-0.parquet/candidates.jsonl.gz"
    candidates = list(rows(candidate))
    candidates[-1]["source_fields"] = dict(address_detail_pid="GAACT-test-77")
    with gzip.open(candidate, "wt") as stream:
        for row in candidates:
            stream.write(json.dumps(row) + "\n")
    protected = tmp_path / "protected.jsonl"
    protected.write_text(
        json.dumps(hf_row(record("90 Protected Road Town"), "VN"))
        + "\n"
        + json.dumps(hf_row(record("90 Protected Road Town 12345", [*tags, "PostalCode"]), "IN"))
        + "\n"
        + json.dumps(
            dict(
                hf_row(record("7 Old Road Oldtown"), "au"),
                source_fields=dict(address_detail_pid="GAACT-test-77"),
            )
        )
        + "\n"
    )
    output = tmp_path / "consolidated"
    result = consolidate(tmp_path, output, [protected])
    assert {r["text"] for r in rows(output / "candidates.jsonl.gz")} == {
        "12-14 Main St Town",
        "1214 Main St Town",
    }
    assert result["counts"]["duplicate_occurrences"] == 2
    reasons = {r["quarantine_reason"] for r in rows(output / "quarantine.jsonl.gz")}
    assert reasons == {"exact-label-conflict", "model-input-label-conflict", "protected-overlap"}
    assert result["counts"]["protected-overlap"] == 4
    with pytest.raises(FileExistsError):
        consolidate(tmp_path, output, [protected])
    # An interrupted export cannot receive a completion report.
    candidate = tmp_path / "audit/in-chunk-0.parquet/candidates.jsonl.gz"
    with gzip.open(candidate, "wt") as stream:
        stream.write("")
    with pytest.raises(ValueError, match="Incomplete candidate stream"):
        consolidate(tmp_path, tmp_path / "broken", [protected])
    assert not (tmp_path / "broken/report.json").exists()
