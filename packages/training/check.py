"""Run invariant checks, CRF enumeration parity, and a small overfit check."""

import argparse
import gzip
import itertools
import json
import tarfile
import tempfile
from pathlib import Path

import torch

from .data import batch, load
from .expand import ban_row, hf_row, numeric, quality_reason
from .model import ARCHITECTURE, Tagger
from .paths import ROOT
from .prepare import identity, prefix_text, review_queue, tagged, validate, variant, web_rows
from .schema import LABELS
from .tokenizer import components, encode


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=ROOT / "data")
    args = ap.parse_args(argv)
    torch.set_num_threads(2)
    torch.manual_seed(7)
    # Large upstream tar members use GNU binary size fields, not ASCII octal.
    with tempfile.TemporaryDirectory() as temp:
        header = tarfile.TarInfo("large.tsv")
        header.size = 80 * 1024**3
        path = Path(temp) / "prefix.gz"
        path.write_bytes(
            gzip.compress(header.tobuf(format=tarfile.GNU_FORMAT) + b"complete row\npartial")
        )
        assert prefix_text(path, tar=True) == "complete row\n"
    mapped = hf_row(
        dict(
            Address="12 Main Street London",
            Tags=["StreetNumber", "StreetName", "StreetName", "Municipality"],
        ),
        "gb",
    )
    assert [(s["label"], s["raw"]) for s in mapped["components"]] == [
        ("house_number", "12"),
        ("road", "Main Street"),
        ("city", "London"),
    ]
    try:
        hf_row(dict(Address="12 Main", Tags=["StreetNumber"]), "gb")
        raise AssertionError("Misaligned tags accepted")
    except ValueError:
        pass
    assert numeric(0.0) == "0" and numeric(12.0) == "12"
    paris = ban_row(
        dict(
            id="fixture",
            numero="12",
            rep="bis",
            nom_voie="Rue Exemple",
            code_postal="75001",
            nom_commune="Paris 1er Arrondissement",
            libelle_acheminement="PARIS",
            code_insee="75101",
            certification_commune="1",
        ),
        "75",
    )
    assert paris["components"][-1]["raw"] == "PARIS" and paris["components"][0]["raw"] == "12bis"
    assert quality_reason(dict(country="sg", text="Pasir Gudang Singapore", components=[]))
    row = tagged("en\tgb\t4/house_number A/B/road |/FSEP London/city")
    row.update(id="fixture", country="gb")
    validate(row)
    assert row["components"][1]["raw"] == "A/B"
    for i in range(30):
        changed = variant(row, i)
        validate(changed)
        item = encode(changed)
        assert item is not None
        assert components(item[1], item[2], changed["text"]) == item[3]["components"]
    combinations = {
        (variant(row, i)["augmentation"]["case"], variant(row, i)["augmentation"]["layout"])
        for i in range(200)
    }
    assert combinations == set(
        itertools.product(["original", "lower", "upper"], ["source", "spaces", "mixed"])
    ), "Case and separator augmentation became coupled"
    chinese = tagged("zh\tcn\t上/city 海/city 市/city 12/house_number 路/road")
    item = encode(chinese)
    assert components(item[1], item[2], chinese["text"]) == item[3]["components"]
    spaced = dict(text="12 Main Street", components=None)
    multiline = dict(text="12\nMain Street", components=None)
    assert encode(spaced, False)[0] == encode(multiline, False)[0]
    assert encode(spaced, False, True)[0] != encode(multiline, False, True)[0]
    with_gaps = encode(chinese, gap_features=True)
    assert components(with_gaps[1], with_gaps[2], chinese["text"]) == with_gaps[3]["components"]
    assert encode(dict(text="1 " + "a" * 64, components=None), False, True) is not None
    quad = '<http://example.org/a> <http://schema.org/streetAddress> "12 Example Road" <https://one.example/> .\n'
    real, invalid = web_rows(quad)
    assert len(real) == 1 and invalid == 0 and real[0]["components"] is None
    real[0]["domain"] = "one.example"
    assert review_queue(real)[0]["review_split"] == "natural-partial"
    fields = dict(
        real[0]["source_fields"],
        addressLocality="Town",
        addressRegion="State",
        postalCode="123",
        addressCountry="US",
    )
    complete = dict(real[0], id="complete", source_fields=fields)
    queue = review_queue([complete])
    assert queue[0]["review_split"] == "natural-partial" and queue[0]["text"] == "12 Example Road"
    # One subject ID used on two pages must not merge their component metadata.
    text = quad.replace("<http://example.org/a>", "_:a")
    text += '_:a <http://schema.org/streetAddress> "15 Other Road" <https://two.example/> .\n'
    real, invalid = web_rows(text)
    assert len(real) == 2 and invalid == 0
    model = Tagger(architecture=ARCHITECTURE)
    emissions = torch.randn(1, 2, len(LABELS))
    lengths = torch.tensor([2])
    trans = model.transitions + model.allowed
    scores = []
    paths = list(itertools.product(range(len(LABELS)), repeat=2))
    for a, b in paths:
        scores.append(
            model.start[a]
            + model.start_allowed[a]
            + emissions[0, 0, a]
            + trans[a, b]
            + emissions[0, 1, b]
            + model.end[b]
        )
    scores = torch.stack(scores)
    expected = list(paths[int(scores.argmax())])
    assert model.decode(emissions, lengths) == [expected]
    gold = torch.tensor([expected])
    assert torch.allclose(
        model.loss(emissions, gold, lengths),
        (torch.logsumexp(scores, 0) - scores.max()) / 2,
        atol=1e-5,
    )
    # Padding must not change emissions or decoding for a short example.
    small = encode(row)
    longer = encode(
        tagged(
            "en\tus\t12/house_number Very/road Long/road Example/road Street/road |/FSEP New/city York/city"
        )
    )
    model.eval()
    x, _, n, _ = batch([small], "cpu")
    alone = model(x, n)
    x2, _, n2, ordered = batch([small, longer], "cpu")
    together = model(x2, n2)
    pos = next(i for i, item in enumerate(ordered) if item[3]["text"] == row["text"])
    assert torch.allclose(alone[0], together[pos, : n[0]], atol=1e-6)
    # A trainable model must learn a tiny fixture, not just return finite tensors.
    model.train()
    x, y, n, _ = batch([small], "cpu")
    optimizer = torch.optim.Adam(model.parameters(), lr=0.03)
    for _ in range(100):
        optimizer.zero_grad()
        loss = model.loss(model(x, n), y, n)
        loss.backward()
        optimizer.step()
    model.eval()
    assert model.decode(model(x, n), n)[0] == small[1]
    if (args.data / "train.jsonl.gz").exists():
        train, rejected_train = load(args.data / "train.jsonl.gz")
        dev, rejected_dev = load(args.data / "dev.jsonl.gz")
        assert train and dev
        assert not ({item[3]["group_id"] for item in train} & {item[3]["group_id"] for item in dev})
        assert not (
            {identity(item[3]["text"]) for item in train}
            & {identity(item[3]["text"]) for item in dev}
        )
        with gzip.open(args.data / "public-benchmark.jsonl.gz", "rt") as source:
            benchmark = {identity(json.loads(line)["text"]) for line in source}
        assert not ({identity(item[3]["text"]) for item in train + dev} & benchmark)
        for item in train + dev:
            validate(item[3])
            assert components(item[1], item[2], item[3]["text"]) == item[3]["components"]
        extra = args.data / "source-dev.jsonl.gz"
        if extra.exists():
            heldout, rejected = load(extra)
            assert rejected == 0
            assert not (
                {item[3]["group_id"] for item in train} & {item[3]["group_id"] for item in heldout}
            )
            assert not (
                {identity(item[3]["text"]) for item in train}
                & {identity(item[3]["text"]) for item in heldout}
            )
        print(
            json.dumps(
                dict(
                    train=len(train),
                    dev=len(dev),
                    rejected_train=rejected_train,
                    rejected_dev=rejected_dev,
                )
            )
        )
    print(
        "PASS: label spans, augmentation, CJK, RDF provenance, CRF brute-force parity, padding, overfit, data splits"
    )


if __name__ == "__main__":
    main()
