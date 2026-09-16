"""Frozen external US diagnostic; reuse existing competitors, never train."""
import hashlib
import importlib.util
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages/training/src"))
from gpu_postal.consolidate import rows
from gpu_postal.evaluate import field_tokens
from gpu_postal.prepare import identity

OUT = ROOT / "data/geosearch-sample-20260916"
REV = "424f94167c21d1ad3f8e70b50a75174f68dfe1f0"
URL = f"https://raw.githubusercontent.com/zhengcongyin/Geocoding-Address-Parsing-Benchmark/{REV}/benchmark_dataset/test.txt"
MAP = dict(HOUSENUM="street_address", STREET="street_address", ROADTYPE="street_address",
           PREDIRECTIONAL="street_address", POSTDIRECTIONAL="street_address",
           CITY="city", STATE="state", POSTAL="postcode")

def save(name, value):
    with (OUT / name).open("x") as f:
        json.dump(value, f, indent=2)

def parse(raw):
    result, tokens, parts = [], [], []
    for line in raw.splitlines() + ["-END-"]:
        if line.startswith("-END-"):
            if tokens:
                result.append(dict(id=str(len(result)), text=" ".join(tokens), components=parts))
                tokens, parts = [], []
        elif line.strip():
            token, tag = line.split()
            label = MAP[tag.split("-", 1)[1]]
            tokens.append(token)
            if parts and parts[-1]["label"] == label:
                parts[-1]["raw"] += " " + token
            else:
                parts.append(dict(label=label, raw=token))
    return result

def prepare():
    assert parse("1 B-HOUSENUM\nMAIN B-STREET\nST B-ROADTYPE\nNY B-CITY\n-END- -X- -X-\n")[0]["components"] == [dict(label="street_address", raw="1 MAIN ST"), dict(label="city", raw="NY")]
    raw = urlopen(URL, timeout=60).read()
    candidates = parse(raw.decode())
    random.Random(20260916).shuffle(candidates)
    # ponytail: normalized exact-text exclusion only; no claim of entity-level independence.
    wanted = {identity(r["text"]) for r in candidates}
    overlaps = set()
    training = ROOT / "data/english-seven-20260916/train.jsonl.gz"
    for r in rows(training):
        if r["country"] == "us":
            key = identity(r["text"])
            if key in wanted:
                overlaps.add(key)
    selected, seen = [], set()
    for r in candidates:
        key = identity(r["text"])
        if key not in overlaps and key not in seen:
            selected.append(r)
            seen.add(key)
        if len(selected) == 1000:
            break
    assert len(selected) == 1000
    OUT.mkdir(exist_ok=False)
    save("inputs.json", selected)
    save("manifest.json", dict(url=URL, source_sha256=hashlib.sha256(raw).hexdigest(),
         seed=20260916, test_rows=len(candidates), overlapping_normalized_texts=len(overlaps),
         sample_rows=len(selected), mapping=MAP, training=str(training),
         limitations="Exact normalized text exclusion only; entity/near-duplicate and competitor overlap unknown. Synthetic US diagnostic, not natural traffic."))
    print("Prepared", len(selected), "from", len(candidates), "overlaps", len(overlaps), flush=True)

def infer(mode):
    records = json.loads((OUT / "inputs.json").read_text())
    if mode in {"ours", "ours12"}:
        import torch
        from gpu_postal.model import Tagger
        from gpu_postal.data import batch
        from gpu_postal.tokenizer import encode, components
        torch.set_num_threads(2)
        epoch = 12 if mode == "ours12" else 8
        path = ROOT / f"runs/ordered-h128-english-seven-20260916/epoch-{epoch}.pt"
        c = torch.load(path, map_location="cpu", weights_only=False)
        m = Tagger(**c["metadata"]["config"])
        m.load_state_dict(c["model"])
        m.eval()
        predictions = []
        with torch.inference_mode():
            for r in records:
                item = encode(r, labeled=False, gap_features=m.config["gap_features"])
                if item is None:
                    predictions.append(dict(id=r["id"], predicted=[]))
                    continue
                x, _, lengths, _ = batch([item], "cpu")
                tags = m.decode(m(x, lengths), lengths)[0]
                predictions.append(dict(id=r["id"], predicted=components(tags, item[2], r["text"])))
        metadata = dict(epoch=c["epoch"], checkpoint=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    else:
        spec = importlib.util.spec_from_file_location("existing", ROOT / "docs/evidence/compare-parsers-20260916.py")
        existing = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(existing)
        predictions, metadata = (existing.deep if mode == "deepparse" else existing.postal)(records)
    save(mode + "-predictions.json", predictions)
    save(mode + "-metadata.json", metadata)

def score(final=False):
    records = json.loads((OUT / "inputs.json").read_text())
    report, paired = {}, {r["id"]: dict(r, parsers={}) for r in records}
    for mode in (("ours", "ours12", "senzing", "deepparse") if final else ("ours", "senzing", "deepparse")):
        predictions = {r["id"]: r["predicted"] for r in json.loads((OUT / (mode + "-predictions.json")).read_text())}
        assert predictions.keys() == paired.keys()
        counts = defaultdict(Counter)
        for r in records:
            truth, got = field_tokens(r["components"]), field_tokens(predictions[r["id"]])
            exact = truth == got
            group = "four_fields_present" if set(truth) == {"street_address", "city", "state", "postcode"} else "partial"
            for key in ("all", group):
                counts[key].update(n=1, exact=int(exact))
            paired[r["id"]]["parsers"][mode] = dict(exact=exact, predicted=predictions[r["id"]])
        report[mode] = dict(counts)
    save("scores12.json" if final else "scores.json", report)
    save("paired12.json" if final else "paired.json", list(paired.values()))
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "prepare":
        prepare()
    elif mode in {"score", "score12"}:
        score(mode == "score12")
    else:
        assert mode in {"ours", "ours12", "senzing", "deepparse"}
        infer(mode)
