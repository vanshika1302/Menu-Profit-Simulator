import random

import pytest

from etl.load import load_all
from etl.warehouse import get_connection
from sim.matrix import ACTIONS, INSUFFICIENT, class_across_bands, class_moves, classify


def item(i, cat, units, cm):
    return {"item_id": i, "category": cat, "units": units, "cm": cm}


# Category X: shares 50/30/20 -> popularity threshold 0.7/3 = 0.2333
X = [item("s", "X", 500, 10), item("p", "X", 300, 4), item("z", "X", 200, 12)]


def test_hand_classification():
    r = classify(X)
    # weighted cm = (5000 + 1200 + 2400) / 1000 = 8.6
    assert r["thresholds"]["X"]["margin_threshold"] == pytest.approx(8.6)
    assert r["thresholds"]["X"]["popularity_threshold"] == pytest.approx(0.7 / 3)
    assert r["items"]["s"]["class"] == "Star"
    assert r["items"]["p"]["class"] == "Plowhorse"
    assert r["items"]["z"]["class"] == "Puzzle"  # share 0.2 < 0.2333, cm 12 >= 8.6


def test_dog_and_ties_go_high():
    items = [item("a", "X", 100, 5), item("b", "X", 100, 5), item("c", "X", 5000, 5), item("d", "X", 60, 1)]
    r = classify(items)["items"]
    assert r["c"]["class"] == "Star"      # popular; cm 5 is above the weighted average
    assert r["a"]["class"] == "Puzzle"    # share 1.9% < 17.5%, cm above threshold
    assert r["d"]["class"] == "Dog"
    # every item at the threshold exactly: cm == threshold counts as high margin
    two = classify([item("a", "X", 100, 5), item("b", "X", 100, 5)])
    assert all(v["class"] == "Star" for v in two["items"].values())


def test_insufficient_data_excluded_from_thresholds():
    items = X + [item("tiny", "X", 49, 100)]
    r = classify(items)
    assert r["items"]["tiny"]["class"] == INSUFFICIENT
    assert r["items"]["tiny"]["share"] is None
    assert r["thresholds"]["X"]["n"] == 3
    assert r["thresholds"]["X"]["margin_threshold"] == pytest.approx(8.6)
    assert classify(items, min_units=49)["items"]["tiny"]["class"] != INSUFFICIENT


def test_scope_toggle():
    items = X + [item("y1", "Y", 900, 20), item("y2", "Y", 100, 2)]
    cat = classify(items, "category")
    menu = classify(items, "menu")
    assert set(cat["thresholds"]) == {"X", "Y"}
    assert set(menu["thresholds"]) == {"menu"}
    assert menu["thresholds"]["menu"]["n"] == 5
    with pytest.raises(ValueError):
        classify(items, "bad")


def test_invariant_to_item_order():
    items = X + [item("y1", "Y", 900, 20), item("y2", "Y", 100, 2), item("y3", "Y", 400, 9)]
    base = classify(items)
    for seed in range(5):
        shuffled = items[:]
        random.Random(seed).shuffle(shuffled)
        assert classify(shuffled) == base


def test_popularity_factor_editable():
    assert classify(X, popularity_factor=0.5)["items"]["z"]["class"] == "Star"


def test_class_moves_show_both_thresholds():
    base = classify(X)
    cut = [item("s", "X", 500, 3), item("p", "X", 300, 4), item("z", "X", 200, 12)]
    moves = class_moves(base, classify(cut))
    assert moves["s"]["moved"] and moves["s"]["baseline_class"] == "Star"
    assert moves["s"]["baseline_thresholds"]["margin"] == pytest.approx(8.6)
    assert moves["s"]["scenario_thresholds"]["margin"] != moves["s"]["baseline_thresholds"]["margin"]
    # p did not change but the margin threshold fell with s's cm: both thresholds are reported
    assert not moves["p"]["moved"] or moves["p"]["scenario_thresholds"]["margin"] < 8.6


def test_class_uncertain_flag():
    medium = classify(X)
    high = classify([item("s", "X", 500, 10), item("p", "X", 300, 4), item("z", "X", 400, 12)])
    out = class_across_bands({"low": medium, "medium": medium, "high": high})
    assert out["z"]["class_uncertain"] and out["z"]["class"] == "Puzzle"
    assert out["z"]["class_by_band"]["high"] != "Puzzle"
    assert out["s"]["class_by_band"]["low"] == out["s"]["class"]
    assert out["s"]["action"] == ACTIONS[out["s"]["class"]]


@pytest.mark.parametrize("scope", ["category", "menu"])
def test_matches_sql_view(scope):
    con = get_connection(":memory:")
    load_all(con)
    df = con.execute("SELECT item_id, category, window_units AS units, cm FROM v_item_cm").df()
    items = df.to_dict("records")
    py = classify(items, scope)["items"]
    sql = con.execute(
        "SELECT item_id, CASE WHEN insufficient_data = 1 THEN 'Insufficient data' "
        "WHEN unit_share >= popularity_threshold AND cm >= margin_threshold THEN 'Star' "
        "WHEN unit_share >= popularity_threshold THEN 'Plowhorse' "
        "WHEN cm >= margin_threshold THEN 'Puzzle' ELSE 'Dog' END AS class "
        "FROM v_matrix_inputs WHERE scope = ?",
        [scope],
    ).fetchall()
    assert {i: c for i, c in sql} == {i: r["class"] for i, r in py.items()}
    assert {r["class"] for r in py.values()} == {"Star", "Plowhorse", "Puzzle", "Dog"}
    con.close()
