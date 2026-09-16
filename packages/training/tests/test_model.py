import pytest
import torch
from training.data import batch
from training.model import ARCHITECTURE, Tagger
from training.tokenizer import encode

DEVICES = ["cpu"] + (["mps"] if torch.backends.mps.is_available() else [])


def item(text):
    return encode(dict(text=text, components=[]))


@pytest.mark.parametrize("device", DEVICES)
def test_ordered_model_ignores_byte_and_token_padding(device):
    torch.manual_seed(7)
    model = Tagger(architecture=ARCHITECTURE).to(device).eval()
    with torch.no_grad():
        model.embedding.weight[0].fill_(3)
        x, _, lengths, _ = batch([item("12 Main")], device)
        expected = model(x, lengths)[0]
        for companion in (item("1234567890123456 Road"), item("1 A B C D E F")):
            x, _, lengths, rows = batch([item("12 Main"), companion], device)
            actual = model(x, lengths)
            position = next(i for i, row in enumerate(rows) if row[3]["text"] == "12 Main")
            assert torch.allclose(expected, actual[position, : len(expected)], atol=1e-5)


def test_ordered_bytes_affect_emissions():
    torch.manual_seed(7)
    model = Tagger(architecture=ARCHITECTURE).eval()
    with torch.no_grad():
        first = model(*batch([item("ab")], "cpu")[:3:2])
        second = model(*batch([item("ba")], "cpu")[:3:2])
    assert not torch.allclose(first, second)


def test_padding_row_stays_zero_after_training_step():
    torch.manual_seed(7)
    model = Tagger(architecture=ARCHITECTURE)
    assert not model.embedding.weight[0].any()
    x, gold, lengths, _ = batch([item("12 Main")], "cpu")
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.01)
    optimizer.zero_grad()
    model.loss(model(x, lengths), gold, lengths).backward()
    optimizer.step()
    assert not model.embedding.weight[0].any()


def test_country_loss_weights_follow_sorted_batch():
    model = Tagger(architecture=ARCHITECTURE)
    x, gold, lengths, _ = batch([item("12 Main Street"), item("London")], "cpu")
    emissions = model(x, lengths)
    losses = [
        model.loss(emissions[i : i + 1], gold[i : i + 1], lengths[i : i + 1]) for i in range(2)
    ]
    expected = (losses[0] * 0.25 + losses[1] * 1.75) / 2
    assert torch.allclose(
        model.loss(emissions, gold, lengths, torch.tensor([0.25, 1.75])), expected
    )


@pytest.mark.parametrize("architecture", [None, "affine-scan-v1", "ordered-byte-h192"])
def test_model_rejects_missing_or_wrong_architecture(architecture):
    with pytest.raises(ValueError, match="Unsupported model architecture"):
        Tagger(architecture=architecture)
