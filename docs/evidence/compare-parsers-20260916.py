"""Run existing parsers on frozen existing evaluation inputs; never train or edit gold."""

import argparse
import ctypes as C
import gzip
import hashlib
import importlib
import importlib.metadata
import json
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/competitor-comparison-20260916"
TOOLS = ROOT / "data/competitor-tools-20260916"
COUNTRIES = {"us", "gb", "za", "nz", "in", "au", "sg"}
COMMON = {"house_number", "road", "unit", "city", "state", "postcode"}
DEEP_MAP = dict(StreetNumber="house_number", StreetName="road", Orientation="road",
                Unit="unit", Municipality="city", Province="state", PostalCode="postcode")
SEVEN_MAP = {
    **dict.fromkeys(("house", "house_number", "road", "unit", "level", "staircase",
                     "entrance", "po_box", "near"), "street_address"),
    **dict.fromkeys(("suburb", "city_district", "island"), "locality"),
    "city": "city", "state_district": "district", "state": "state",
    "country_region": "state", "postcode": "postcode", "country": "country",
    "category": None, "world_region": None,
}


def token_fields(parts, coarse=False):
    # Public gold components are field-ordered, not necessarily input-ordered.
    # ponytail: compare token multiplicities, not order; retain span/order checks for release evaluation.
    result = defaultdict(Counter)
    for part in parts:
        label = SEVEN_MAP[part["label"]] if coarse else part["label"]
        if label is not None:
            tokens = re.findall(r"\w+|[^\w\s,]", unicodedata.normalize("NFKC", part["raw"]).casefold())
            if tokens:
                result[label].update(tokens)
    return dict(result)


def score_seven(rows):
    example = [dict(label="unit", raw="1001 B wing"), dict(label="level", raw="10th floor"),
               dict(label="house", raw="Rustomjee orinana")]
    merged = [dict(label="road", raw="1001 B wing, 10th floor, Rustomjee orinana")]
    assert token_fields(example, True) == token_fields(merged, True)
    assert token_fields(example) != token_fields(merged)
    assert token_fields([dict(label="city", raw="New Haven")], True) != token_fields([dict(label="state", raw="New Haven")], True)
    assert token_fields([dict(label="road", raw="Main Main")], True) != token_fields([dict(label="road", raw="Main")], True)
    report, paired = {}, []
    sources = [OUT / (name + "-predictions.jsonl") for name in
               ("h128-epoch1", "h128-epoch2", "libpostal-senzing")]
    for path in sources:
        records = read(path)
        predictions = {p["id"]: p["predicted"] for p in records}
        assert len(predictions) == len(records) == len(rows)
        assert predictions.keys() == {r["id"] for r in rows}
        groups = defaultdict(Counter)
        for row in rows:
            gold, pred = row["components"], predictions[row["id"]]
            old = fields(gold) == fields(pred)
            fine = token_fields(gold) == token_fields(pred)
            coarse = token_fields(gold, True) == token_fields(pred, True)
            assert not fine or coarse
            for key in (row["evaluation_set"], row["evaluation_set"]+":"+row["country"]):
                groups[key].update(rows=1, original_exact=int(old), fine_token_exact=int(fine),
                                   seven_token_exact=int(coarse), merge_only_gain=int(coarse and not fine))
            paired.append(dict(id=row["id"], model=path.stem, fine_exact=fine, seven_exact=coarse,
                gold=token_fields(gold, True), predicted=token_fields(pred, True)))
        report[path.stem] = dict(groups)
    save("seven-label-scores.json", dict(mapping=SEVEN_MAP, models=report,
         metric="Exact per-field token multisets; NFKC/casefold; commas/whitespace ignored; other punctuation and token counts retained. No ordering or span accuracy claim.",
         inputs_sha256=sha(OUT / "inputs.jsonl"), prediction_hashes={p.name: sha(p) for p in sources},
         script_sha256=sha(Path(__file__)),
         gold_label_counts=dict(Counter(c["label"] for r in rows for c in r["components"]))))
    write("seven-label-paired.jsonl", paired)
    print(json.dumps(report, indent=2))


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def read(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt") as f:
        return [json.loads(line) for line in f]


def write(name, records):
    path = OUT / name
    with path.open("x") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def save(name, value):
    with (OUT / name).open("x") as f:
        json.dump(value, f, indent=2, ensure_ascii=False)


def fields(parts, common=False):
    result = {}
    for part in parts:
        key = part["label"]
        if common and key not in COMMON:
            continue
        value = unicodedata.normalize("NFKC", part["raw"]).casefold()
        if common:
            value = value.replace(",", " ")
        value = " ".join(value.split())
        result[key] = (result.get(key, "") + " " + value).strip()
    return result


def prepare():
    OUT.mkdir(exist_ok=False)
    paths = [("public", ROOT / "data/multisource/public-benchmark.jsonl.gz"),
             ("india-pilot", ROOT / "data/india-expansion-20260915/reviewed/accepted.jsonl")]
    paths += [("natural", ROOT / p) for p in (
        "docs/evidence/natural-ai-review.jsonl", "docs/evidence/natural-complete-ai-review.jsonl",
        "data/latin-20260915/natural-v1/dev.jsonl.gz", "data/latin-20260915/natural-v1/test.jsonl.gz")]
    result = []
    for dataset, path in paths:
        for i, r in enumerate(read(path)):
            country = (r.get("country") or "").lower()
            country = {"usa": "us", "uk": "gb", "india": "in"}.get(country, country)
            if country not in COUNTRIES or r.get("annotation_status", "accepted") not in ("accepted",):
                continue
            result.append(dict(r, id=f"{dataset}/{path.name}/{i}/{r.get('id', '')}",
                               country=country, evaluation_set=dataset))
    assert len({r["id"] for r in result}) == len(result)
    write("inputs.jsonl", result)
    save("inputs-manifest.json", dict(inputs={str(p): sha(p) for _, p in paths},
        rows=len(result), counts=dict(Counter(r["evaluation_set"]+":"+r["country"] for r in result)),
        frozen_input_sha256=sha(OUT / "inputs.jsonl"),
        limits="Existing diagnostics, not new blind release test. Baseline training overlap is unknown; Senzing public set was used by its maintainers. No country hints passed."))
    print("Frozen inputs", len(result), flush=True)


def h128(rows, epoch):
    import torch
    torch.set_num_threads(1)
    run = ROOT / "runs/ordered-h128-case-v6-scratch-20260915"
    sys.path.insert(0, str(run))
    data, tok, model_mod = [importlib.import_module("source." + n) for n in ("data", "tokenizer", "model")]
    path = run / f"epoch-{epoch}.pt"
    saved = torch.load(path, map_location="cpu", weights_only=False)
    for name, expected in saved["metadata"]["code_sha256"].items():
        assert sha(run / "source" / name) == expected
    model = model_mod.Tagger(**saved["metadata"]["config"])
    model.load_state_dict(saved["model"])
    model.eval()
    result = []
    with torch.inference_mode():
        for i in range(0, len(rows), 32):
            items = [tok.encode(r, labeled=False) for r in rows[i:i+32]]
            assert all(x is not None for x in items)
            x, _, lengths, items = data.batch(items, "cpu")
            for tags, (_, _, offsets, row) in zip(model.decode(model(x, lengths), lengths), items):
                result.append(dict(id=row["id"], predicted=tok.components(tags, offsets, row["text"])))
    return result, dict(checkpoint=str(path), sha256=sha(path), epoch=epoch)


def deep(rows):
    import torch
    from deepparse.parser import AddressParser
    torch.set_num_threads(2)
    cache = TOOLS / "deepparse-cache"
    parser = AddressParser(model_type="bpemb", attention_mechanism=True, device="cpu", cache_dir=str(cache), verbose=False)
    result = []
    for i in range(0, len(rows), 64):
        subset = rows[i:i+64]
        predictions = parser([r["text"] for r in subset], batch_size=32, num_workers=0)
        assert len(predictions) == len(subset)
        for row, p in zip(subset, predictions):
            assert p.raw_address == row["text"], "Prediction order/input changed"
            native = [dict(raw=raw, label=tag) for raw, tag in p.address_parsed_components]
            result.append(dict(id=row["id"], native=native,
                predicted=[dict(raw=p["raw"], label=DEEP_MAP.get(p["label"], "deepparse:"+p["label"])) for p in native]))
        print("Deepparse", min(i+64, len(rows)), "/", len(rows), flush=True)
    return result, dict(version=importlib.metadata.version("deepparse"), model="BPEmb+attention", preprocessing="upstream defaults: lowercase, commas removed", mapping=DEEP_MAP,
                        cache_hashes={str(p): sha(p) for p in cache.rglob("*") if p.is_file()})


def postal(rows):
    sys.path.insert(0, str(ROOT / "packages/training/src"))
    from gpu_postal.teacher import Options, Response
    path = TOOLS / "libpostal-src/src/.libs/libpostal.dylib"
    lib = C.CDLL(str(path))
    resources = TOOLS / "senzing-data"
    for name in ("libpostal_setup_datadir", "libpostal_setup_parser_datadir", "libpostal_setup_language_classifier_datadir"):
        fn = getattr(lib, name)
        fn.argtypes, fn.restype = [C.c_char_p], C.c_bool
        assert fn(str(resources).encode()), name
    lib.libpostal_get_address_parser_default_options.restype = Options
    lib.libpostal_parse_address.argtypes = [C.c_char_p, Options]
    lib.libpostal_parse_address.restype = C.POINTER(Response)
    lib.libpostal_address_parser_response_destroy.argtypes = [C.POINTER(Response)]
    options = lib.libpostal_get_address_parser_default_options()
    result = []
    for row in rows:
        response = lib.libpostal_parse_address(row["text"].encode(), options)
        if not response:
            raise RuntimeError("libpostal returned null")
        try:
            parts = [dict(raw=response.contents.components[i].decode(), label=response.contents.labels[i].decode()) for i in range(response.contents.num_components)]
            result.append(dict(id=row["id"], predicted=parts))
        finally:
            lib.libpostal_address_parser_response_destroy(response)
    return result, dict(model="Senzing", parser_version="v1.2.0", base_language_version="v1.1.0", library_sha256=sha(path),
                        archive_hashes={p.name: sha(p) for p in TOOLS.glob("senzing-*.tar.gz")})


def score(rows):
    report = {}
    joined = {r["id"]: dict(r, parsers={}) for r in rows}
    for path in sorted(OUT.glob("*-predictions.jsonl")):
        predictions = {r["id"]: r for r in read(path)}
        assert predictions.keys() == joined.keys(), path
        groups = defaultdict(Counter)
        for row in rows:
            p = predictions[row["id"]]["predicted"]
            exact = fields(p) == fields(row["components"])
            common = fields(p, True) == fields(row["components"], True)
            eligible = {c["label"] for c in row["components"]} <= COMMON
            for key in (row["evaluation_set"], row["evaluation_set"]+":"+row["country"]):
                c = groups[key]
                c["rows"] += 1
                c["full_field_exact"] += exact
                c["common_six_exact"] += common
                c["gold_common_only_rows"] += eligible
                c["gold_common_only_exact"] += eligible and common
            joined[row["id"]]["parsers"][path.stem] = dict(predicted=p, full_exact=exact, common_exact=common)
        report[path.stem] = dict(groups)
    save("scores.json", report)
    write("paired-predictions.jsonl", joined.values())
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "h128-epoch1", "h128-epoch2", "deepparse", "libpostal-senzing", "score", "score-seven"))
    args = parser.parse_args()
    assert fields([dict(label="city", raw=" NEW  YORK ")]) == {"city": "new york"}
    assert fields([dict(label="road", raw="Main, Road"), dict(label="house", raw="X")], True) == {"road": "main road"}
    if args.mode == "prepare":
        prepare()
    else:
        inputs = read(OUT / "inputs.jsonl")
        if args.mode == "score-seven":
            score_seven(inputs)
        elif args.mode == "score":
            score(inputs)
        else:
            started = time.monotonic()
            if args.mode.startswith("h128"):
                result, metadata = h128(inputs, int(args.mode[-1]))
            else:
                result, metadata = (deep if args.mode == "deepparse" else postal)(inputs)
            write(args.mode + "-predictions.jsonl", result)
            save(args.mode + "-metadata.json", dict(metadata, rows=len(result), elapsed_including_setup_s=time.monotonic()-started,
                input_sha256=sha(OUT / "inputs.jsonl"), script_sha256=sha(Path(__file__))))
