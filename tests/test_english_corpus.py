import runpy
from pathlib import Path

from gpu_postal.prepare import group, tagged


def test_english_scope_and_group_split():
    helper = runpy.run_path(
        str(Path(__file__).parents[1] / "docs/evidence/prepare-english-seven-20260916.py")
    )
    english, split = helper["english"], helper["split_for"]
    assert english({"language": "eng"})
    assert english({"language": "", "label_provenance": "generated-from-fields"})
    assert not english({"language": "fr"})
    assert not english({"language": "unk"})
    first = tagged("en\tgb\t12/house_number Main/road Street/road |/FSEP London/city")
    second = tagged("en\tgb\t14/house_number Main/road Street/road |/FSEP London/city")
    assert group(first) == group(second)
    assert split(group(first)) == split(group(second))
    assert set(split(str(i)) for i in range(1000)) == {"train", "dev", "test"}
