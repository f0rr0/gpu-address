import pytest
from gpu_postal.diagnose import saved_exact
from gpu_postal.evaluate import evaluate, field_exact
from gpu_postal.prepare import tagged
from gpu_postal.tokenizer import encode


class ExactModel:
    def __init__(self, paths=()):
        self.paths = paths

    def eval(self):
        return self

    def __call__(self, _x, _lengths):
        return None

    def decode(self, _emissions, lengths):
        return [path[:length] for path, length in zip(self.paths, lengths)]


def test_evaluation_denominators():
    row = tagged("en\tgb\t12/house_number Main/road") | {"id": "one"}
    encoded = encode(row)
    model = ExactModel([encoded[1]])
    result = evaluate(model, [encoded], "cpu", unsupported=1)
    assert result["exact_accuracy"] == result["ordered_span_accuracy_supported"] == 1
    assert result["ordered_span_accuracy_all_inputs"] == 0.5
    assert (result["evaluated"], result["unsupported"], result["total"]) == (1, 1, 2)

    rejected = evaluate(model, [], "cpu", unsupported=2)
    assert (rejected["evaluated"], rejected["unsupported"], rejected["total"]) == (0, 2, 2)
    assert rejected["ordered_span_accuracy_supported"] == 0
    assert rejected["ordered_span_accuracy_all_inputs"] == 0

    sampled = evaluate(model, [encoded], "cpu", unsupported=None)
    assert sampled["exact_accuracy"] == 1
    assert sampled["unsupported"] is sampled["total"] is None
    assert sampled["ordered_span_accuracy_all_inputs"] is None
    empty = evaluate(model, [], "cpu")
    assert empty["evaluated"] == empty["total"] == 0

    for invalid in (-1, 1.5, True):
        with pytest.raises(ValueError, match="unsupported"):
            evaluate(model, [], "cpu", unsupported=invalid)


def test_seven_field_public_scoring_projects_old_gold_and_uses_token_multisets():
    old_gold = [
        {"label": "house_number", "raw": "12"},
        {"label": "road", "raw": "Main, Road"},
        {"label": "city_district", "raw": "West End"},
        {"label": "city", "raw": "Delhi"},
    ]
    predicted = [
        {"label": "city", "raw": "DELHI"},
        {"label": "locality", "raw": "end west"},
        {"label": "street_address", "raw": "road 12 main"},
    ]
    assert field_exact(predicted, old_gold)
    assert not field_exact(predicted + [{"label": "city", "raw": "Delhi"}], old_gold)
    assert saved_exact({"teacher_components": predicted, "exact": False}, old_gold) is True
    assert saved_exact({"exact": True}, old_gold) is None
