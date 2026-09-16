from training.check import main
from training.rank_diagnosis import check


def test_model_and_data_invariants(tmp_path):
    main(["--data", str(tmp_path)])
    check()
