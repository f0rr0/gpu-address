"""Reproduce website comparisons on Senzing's published development benchmark.

Run from the repo root. prepare/gpu/senzing/libpostal/size/report use `uv run python`;
deep uses the existing comparator venv with PYTHONPATH=packages. No training.
"""

import argparse
import csv
import ctypes as C
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data/website-benchmark"
TOOLS = ROOT / "data/competitor-tools-20260916"
COUNTRIES = {
    "us": "US",
    "gb": "UK",
    "au": "Australia",
    "nz": "New Zealand",
    "ca": "Canada",
    "ie": "Ireland",
    "za": "South Africa",
}
SOURCE = "https://raw.githubusercontent.com/Senzing/libpostal-data/5113929832ac06619d18a4816f78a90fef8cc7a3/files/tests/v1.2.0/test_data.csv"


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def save(name, value):
    (OUT / f"{name}.json").write_text(json.dumps(value, indent=2))


def prepare():
    from urllib.request import urlopen

    from training.schema import SOURCE_FIELDS

    path = OUT / "source.csv"
    if not path.exists():
        with urlopen(SOURCE, timeout=60) as response:
            path.write_bytes(response.read())
    assert sha(path) == "db58065bf7508b862e9c6ee68774312bfc7e675192e21b8ee6aa9f7aa32ed51a"
    rows = [
        dict(
            id=r["record_id"],
            text=r["full_address"],
            country=r["country_code"],
            components=[dict(label=k, raw=r[k]) for k in SOURCE_FIELDS if r.get(k)],
        )
        for r in csv.DictReader(path.open())
        if r["country_code"] in COUNTRIES
    ]
    assert len({r["id"] for r in rows}) == len(rows)
    save("inputs", rows)
    save(
        "source",
        dict(url=SOURCE, sha256=sha(path), counts=dict(Counter(r["country"] for r in rows))),
    )


def gpu(rows):
    import torch
    from training.data import batch
    from training.export import serialize
    from training.model import Tagger
    from training.tokenizer import components, encode

    checkpoint = torch.load(
        ROOT / "runs/ordered-h128-english-seven-20260916/best.pt",
        map_location="cpu",
        weights_only=False,
    )
    model = Tagger(**checkpoint["metadata"]["config"])
    model.load_state_dict(checkpoint["model"])
    blob, model, _ = serialize(model.eval(), quantized=True, bits=5)
    assert hashlib.sha256(blob).hexdigest() == sha(ROOT / "packages/core/model.bin")
    result = {}
    with torch.inference_mode():
        for i in range(0, len(rows), 64):
            encoded = [encode(r, False, model.config["gap_features"]) for r in rows[i : i + 64]]
            for row, item in zip(rows[i : i + 64], encoded):
                if item is None:
                    result[row["id"]] = []
            supported = [r for r in encoded if r is not None]
            if not supported:
                continue
            x, _, lengths, items = batch(supported, "cpu")
            paths = model.decode(model(x, lengths), lengths)
            for tags, (_, _, offsets, row) in zip(paths, items):
                result[row["id"]] = components(tags, offsets, row["text"])
    return result


def postal(rows, name):
    from training.teacher import Options, Response

    lib = C.CDLL(str(TOOLS / "libpostal-src/src/.libs/libpostal.dylib"))
    resource = TOOLS / ("senzing-data" if name == "senzing" else "default-data")
    for name in (
        "libpostal_setup_datadir",
        "libpostal_setup_parser_datadir",
        "libpostal_setup_language_classifier_datadir",
    ):
        fn = getattr(lib, name)
        fn.argtypes, fn.restype = [C.c_char_p], C.c_bool
        assert fn(str(resource).encode()), name
    lib.libpostal_get_address_parser_default_options.restype = Options
    lib.libpostal_parse_address.argtypes = [C.c_char_p, Options]
    lib.libpostal_parse_address.restype = C.POINTER(Response)
    lib.libpostal_address_parser_response_destroy.argtypes = [C.POINTER(Response)]
    options = lib.libpostal_get_address_parser_default_options()
    result = {}
    for row in rows:
        response = lib.libpostal_parse_address(row["text"].encode(), options)
        if not response:
            raise RuntimeError("libpostal returned null")
        try:
            result[row["id"]] = [
                dict(
                    raw=response.contents.components[i].decode(),
                    label=response.contents.labels[i].decode(),
                )
                for i in range(response.contents.num_components)
            ]
        finally:
            lib.libpostal_address_parser_response_destroy(response)
    return result


def deep(rows):
    import torch
    from deepparse.parser import AddressParser  # ty: ignore[unresolved-import] -- comparator venv

    torch.set_num_threads(2)
    mapping = dict(
        StreetNumber="house_number",
        StreetName="road",
        Orientation="road",
        Unit="unit",
        Municipality="city",
        Province="state",
        PostalCode="postcode",
    )
    parser = AddressParser(
        model_type="bpemb",
        attention_mechanism=True,
        device="cpu",
        cache_dir=str(TOOLS / "deepparse-cache"),
        verbose=False,
    )
    result = {}
    for i in range(0, len(rows), 64):
        subset = rows[i : i + 64]
        predictions = parser([r["text"] for r in subset], batch_size=32, num_workers=0)
        assert len(predictions) == len(subset)
        for row, prediction in zip(subset, predictions):
            assert prediction.raw_address == row["text"]
            result[row["id"]] = [
                dict(raw=raw, label=mapping[tag])
                for raw, tag in prediction.address_parsed_components
            ]
        print("Deepparse", min(i + 64, len(rows)), flush=True)
    return result


def sizes():
    import brotli

    cache = TOOLS / "deepparse-cache"
    paths = {
        "gpu": [ROOT / "packages/core/model.bin"],
        "deepparse": [
            cache
            / "models--deepparse--bpemb-attention/snapshots/4af74dad1d547804dfc2de8f40fb23fbbec5b811/model.safetensors",
            *sorted((cache / "multi").glob("*")),
        ],
        "senzing": sorted((TOOLS / "senzing-data").rglob("*.dat"))
        + sorted((TOOLS / "senzing-data").rglob("*.trie")),
        "libpostal": sorted((TOOLS / "default-data").rglob("*.dat"))
        + sorted((TOOLS / "default-data").rglob("*.trie")),
    }
    result = {}
    for model, files in paths.items():
        assert files, model
        assets = []
        total = 0
        for path in files:
            compressor = brotli.Compressor(quality=5)
            count = 0
            with path.open("rb") as f:
                while chunk := f.read(1024 * 1024):
                    count += len(compressor.process(chunk))
            count += len(compressor.finish())
            total += count
            assets.append(dict(file=path.name, sha256=sha(path), brotli_bytes=count))
            print(model, path.name, count, flush=True)
        result[model] = dict(bytes=total, files=assets)
        save("sizes", result)


def report(rows):
    from training.evaluate import field_exact

    models = ("gpu", "libpostal", "senzing", "deepparse")
    predictions = {m: json.loads((OUT / f"{m}.json").read_text()) for m in models}
    assert all(set(p) == {r["id"] for r in rows} for p in predictions.values())
    groups = defaultdict(lambda: Counter(rows=0))
    # Shared four-field view includes only gold whose mapped labels are supported by all.
    from training.evaluate import field_tokens

    shared = defaultdict(lambda: Counter(rows=0))
    complete = defaultdict(lambda: Counter(rows=0))
    partial = defaultdict(lambda: Counter(rows=0))
    supported = {"street_address", "city", "state", "postcode"}
    for row in rows:
        c = row["country"]
        groups[c]["rows"] += 1
        eligible = set(field_tokens(row["components"])) <= supported
        if eligible:
            shared[c]["rows"] += 1
            cohort = complete[c] if set(field_tokens(row["components"])) == supported else partial[c]
            cohort["rows"] += 1
        for m in models:
            correct = field_exact(predictions[m][row["id"]], row["components"])
            groups[c][m] += correct
            if eligible:
                shared[c][m] += correct
                cohort[m] += correct
    result = dict(
        source=json.loads((OUT / "source.json").read_text()),
        metric="Exact per-field token multisets: NFKC/casefold, commas and whitespace ignored, other punctuation and token counts retained. All seven fields scored; missing fields count as errors.",
        limitations="Senzing public development benchmark; previously inspected, not blind or independently unseen. Competitor training overlap unknown. Deepparse has no locality, district or country labels; see shared-field subset.",
        models=dict(
            gpu="gpu-postal int5 experimental.2 (Python reconstruction of release weights)",
            libpostal="libpostal default v1.0.0",
            senzing="libpostal Senzing v1.2",
            deepparse="Deepparse 0.10.0 BPEmb + attention",
        ),
        countries=[
            dict(country=c, name=name, **groups[c], shared=dict(shared[c]),
                 complete={k: complete[c][k] for k in ("rows", *models)},
                 partial={k: partial[c][k] for k in ("rows", *models)})
            for c, name in COUNTRIES.items()
        ],
        sizes=json.loads((OUT / "sizes.json").read_text()),
        compression="Brotli quality 5, each asset independently; model/data assets only, excludes code and frameworks. Deepparse includes BPEmb embeddings and tokenizer; libpostal includes parser, dictionaries and language classifier.",
        prediction_sha256={m: sha(OUT / f"{m}.json") for m in models},
    )
    target = ROOT / "apps/website/public/benchmarks.json"
    target.write_text(json.dumps(result, indent=2))
    print(json.dumps(result["countries"], indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "mode", choices=["prepare", "gpu", "libpostal", "senzing", "deep", "sizes", "report"]
    )
    mode = ap.parse_args().mode
    OUT.mkdir(exist_ok=True)
    if mode == "prepare":
        prepare()
    elif mode == "sizes":
        sizes()
    else:
        rows = json.loads((OUT / "inputs.json").read_text())
        if mode == "report":
            report(rows)
        elif mode == "gpu":
            save("gpu", gpu(rows))
        elif mode == "deep":
            save("deepparse", deep(rows))
        else:
            save(mode, postal(rows, mode))
