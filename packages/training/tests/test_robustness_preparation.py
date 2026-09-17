import importlib
from collections import Counter

p = importlib.import_module("training.scripts.prepare_robustness")


def row(text="12 Main Street, Austin, TX", reordered=False, row_id="r1"):
    if text == "13 Oak Road, Austin, TX":
        parts = [("house_number", "13"), ("road", "Oak Road"), ("city", "Austin"), ("state", "TX")]
    elif not reordered:
        parts = [
            ("house_number", "12"),
            ("road", "Main Street"),
            ("city", "Austin"),
            ("state", "TX"),
        ]
    else:
        text = "Austin, TX | 12 Main Street"
        parts = [
            ("city", "Austin"),
            ("state", "TX"),
            ("house_number", "12"),
            ("road", "Main Street"),
        ]
    spans = []
    pos = 0
    for label, raw in parts:
        start = text.index(raw, pos)
        spans.append({"label": label, "raw": raw, "start": start, "end": start + len(raw)})
        pos = start + len(raw)
    return {"id": row_id, "country": "us", "text": text, "components": spans}


def db(tmp_path):
    import sqlite3

    conn = sqlite3.connect(tmp_path / "selection.sqlite")
    p.initialize(conn)
    return conn


def test_protected_group_blocks_admission(tmp_path):
    conn = db(tmp_path)
    candidate = row()
    conn.execute("INSERT INTO groups VALUES (?, 'protected')", (p.group(candidate),))
    counts = Counter()
    p.admit(conn, candidate, counts)
    assert counts["heldout_group"] == 1
    assert conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0] == 0


def test_existing_train_and_heldout_splits_are_preserved(tmp_path):
    conn = db(tmp_path)
    train = row(row_id="train")
    conn.execute("INSERT INTO groups VALUES (?, 'train')", (p.group(train),))
    counts = Counter()
    p.admit(conn, train, counts)
    assert conn.execute("SELECT split FROM candidates").fetchone()[0] == "train"

    heldout = row(text="13 Oak Road, Austin, TX", row_id="dev")
    # Protect the exact existing street/entity group as dev.
    conn.execute("INSERT INTO groups VALUES (?, 'dev')", (p.group(heldout),))
    p.admit(conn, heldout, counts)
    assert counts["heldout_group"] == 1


def test_conflicting_same_text_annotations_mark_candidate_conflict(tmp_path):
    conn = db(tmp_path)
    first = row(row_id="first")
    second = row(row_id="second")
    second["components"][2]["label"] = "locality"
    counts = Counter()
    p.admit(conn, first, counts)
    p.admit(conn, second, counts)
    assert counts["duplicate"] == 1
    assert conn.execute("SELECT conflict FROM candidates").fetchone()[0] == 1


def test_reordered_same_entity_is_not_admitted_as_second_candidate(tmp_path):
    conn = db(tmp_path)
    counts = Counter()
    p.admit(conn, row(row_id="first"), counts)
    p.admit(conn, row(reordered=True, row_id="reordered"), counts)
    assert counts["duplicate"] == 1
    assert conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0] == 1


def test_new_group_split_bridge_is_rejected(tmp_path):
    conn = db(tmp_path)
    candidate = row()
    aliases = p.keys(candidate) | {p.group(candidate)}
    first, second = sorted(aliases)[:2]
    conn.execute("INSERT INTO new_groups VALUES (?, 'train')", (first,))
    conn.execute("INSERT INTO new_groups VALUES (?, 'dev')", (second,))
    counts = Counter()
    p.admit(conn, candidate, counts)
    assert counts["cross_source_split_bridge"] == 1


def test_us_pilot_gate_does_not_let_aggregate_hide_zip_failure():
    from training.scripts.review_us_candidate import gate

    def panel(n):
        return {"countries": {"us": {"exact": n, "rows": 1000}}}

    baseline = {
        name: panel(900)
        for name in ("clean", "old-us", "new-us", "partial", "reordered", "combined")
    }
    baseline["zip-first"] = panel(0)
    candidate = {name: panel(950) for name in baseline}
    assert gate(candidate, baseline, pilot=True) == (True, [])
    candidate["zip-first"] = panel(799)
    assert gate(candidate, baseline, pilot=True) == (False, ["zip-first"])
    candidate["zip-first"] = panel(950)
    candidate["clean"] = panel(894)
    assert "clean-country-macro" in gate(candidate, baseline, pilot=True)[1]
