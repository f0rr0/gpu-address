from gpu_address.check import main
from gpu_address.rank_diagnosis import check


def test_model_and_data_invariants(tmp_path):
    main(["--data", str(tmp_path)])
    check()
