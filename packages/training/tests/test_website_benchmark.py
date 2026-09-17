"""The public chart snapshot must retain denominators and asset accounting."""

import json
from pathlib import Path


def test_website_benchmark_snapshot():
    path = Path(__file__).resolve().parents[3] / "apps/website/public/benchmarks.json"
    report = json.loads(path.read_text())
    assert {r["country"] for r in report["countries"]} == {"us", "gb", "au", "nz", "ca", "ie", "za"}
    assert sum(r["rows"] for r in report["countries"]) == 3151
    for row in report["countries"]:
        assert 0 < row["shared"]["rows"] <= row["rows"]
        for key in ("rows", *report["models"]):
            assert row["complete"][key] + row["partial"][key] == row["shared"][key]
        for model in report["models"]:
            assert 0 <= row[model] <= row["rows"]
            assert 0 <= row["shared"][model] <= min(row[model], row["shared"]["rows"])
    for item in report["sizes"].values():
        assert item["bytes"] == sum(asset["brotli_bytes"] for asset in item["files"])
    assert "not blind" in report["limitations"]
    uk = next(r for r in report["countries"] if r["country"] == "gb")
    assert uk["complete"]["rows"] == 1
    assert all(uk["complete"][model] == 0 for model in report["models"])
