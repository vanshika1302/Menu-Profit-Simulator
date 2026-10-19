import math

import pytest

from etl.baseline import baseline_from_warehouse
from etl.load import load_all
from etl.warehouse import get_connection
from sim import model
from sim.scenarios import run_scenario


@pytest.fixture(scope="module")
def base():
    con = get_connection(":memory:")
    load_all(con)
    b = baseline_from_warehouse(con)
    con.close()
    return b


BEEF = ["ribeye", "sirloin", "short_rib", "ground_beef", "shaved_beef"]


def test_cost_shock_alone_identical_across_bands(base):
    r = run_scenario(base, {"cost_shock": {i: 0.20 for i in BEEF}})
    lo, me, hi = (r["total"]["by_band"][b] for b in ("low", "medium", "high"))
    assert lo == me == hi
    assert r["total"]["profit_change_range"]["low"] == r["total"]["profit_change_range"]["high"] < 0
    assert all(i["price_test"] is None for i in r["items"].values())


def test_beef_shock_hits_seven_items_only(base):
    r = run_scenario(base, {"cost_shock": {i: 0.20 for i in BEEF}})
    hit = [i for i, v in r["items"].items() if v["by_band"]["medium"]["profit_change"] < 0]
    assert len(hit) == 7


def test_empty_scenario_is_baseline(base):
    r = run_scenario(base, {})
    assert r["total"]["profit_change_range"] == {"low": pytest.approx(0, abs=1e-8), "high": pytest.approx(0, abs=1e-8)}
    assert not any(v["matrix"]["moved"] for v in r["items"].values())


def test_price_rise_range_orders_with_elasticity(base):
    r = run_scenario(base, {"price_change": {"ribeye": 0.05}, "substitution": 0.0})
    ch = [r["items"]["ribeye"]["by_band"][b]["profit_change"] for b in ("low", "medium", "high")]
    assert ch[0] > ch[1] > ch[2]
    rng = r["total"]["profit_change_range"]
    assert rng["low"] == pytest.approx(ch[2]) and rng["high"] == pytest.approx(ch[0])
    assert r["total"]["annual_profit_change_range"]["high"] == pytest.approx(52 * ch[0])


def test_price_test_fields_and_verdict(base):
    r = run_scenario(base, {"price_change": {"ribeye": 0.05}})
    t = r["items"]["ribeye"]["price_test"]
    it = next(i for i in base["items"] if i["item_id"] == "ribeye")
    cost = model.unit_costs(base["recipes"], base["ingredient_costs"])["ribeye"]
    assert t["break_even_elasticity"] == pytest.approx(model.break_even_elasticity(it["price"], it["price"] * 1.05, cost))
    assert t["break_even_drop"] == pytest.approx(model.break_even_drop(it["price"], it["price"] * 1.05, cost))
    assert t["break_even_drop_net"] != t["break_even_drop"]
    assert 0 < t["by_band"]["medium"]["predicted_drop"] < t["by_band"]["high"]["predicted_drop"]
    # eps* is about -1.63: inside the default band (-0.5 to -1.8), so the high band loses
    assert t["break_even_elasticity"] == pytest.approx(-1.63, abs=0.01)
    assert t["verdict"] == "pays off only if demand is less elastic than -1.63"
    assert [t["by_band"][b]["own_profit_change"] > 0 for b in ("low", "medium", "high")] == [True, True, False]
    safe = run_scenario(base, {"price_change": {"ribeye": 0.05}, "bands": {"low": -0.3, "medium": -0.6, "high": -1.2}})
    assert safe["items"]["ribeye"]["price_test"]["verdict"] == "pays off under all bands"


def test_verdict_mixed_and_losing(base):
    # a rise on a thin-margin item breaks even inside the band
    r = run_scenario(base, {"price_change": {"classic_burger": 0.10}})
    v = r["items"]["classic_burger"]["price_test"]
    assert v["break_even_elasticity"] == pytest.approx(
        math.log((16 - 6.26) / (17.6 - 6.26)) / math.log(1.1), abs=0.05
    )
    # force the loss and the mixed case with custom bands
    lose = run_scenario(base, {"price_change": {"ribeye": 0.05}, "bands": {"low": -4.0, "medium": -5.0, "high": -6.0}})
    assert lose["items"]["ribeye"]["price_test"]["verdict"] == "loses money under all bands"
    mixed = run_scenario(base, {"price_change": {"ribeye": 0.05}, "bands": {"low": -1.0, "medium": -2.0, "high": -4.0}})
    t = mixed["items"]["ribeye"]["price_test"]
    assert t["verdict"].startswith("pays off only if demand is less elastic than -1.63")


def test_price_cut_verdict_direction(base):
    r = run_scenario(base, {"price_change": {"ribeye": -0.05}, "bands": {"low": -1.0, "medium": -2.0, "high": -4.0}})
    t = r["items"]["ribeye"]["price_test"]
    assert "more elastic" in t["verdict"]


def test_category_price_change_and_item_override(base):
    r = run_scenario(base, {"category_price_change": {"Entrees": 0.05}, "price_change": {"ribeye": 0.0}})
    changed = set(r["price_changes"])
    entrees = {i["item_id"] for i in base["items"] if i["category"] == "Entrees"}
    assert changed == entrees - {"ribeye"}


def test_pass_through(base):
    r = run_scenario(base, {"cost_shock": {"ribeye": 0.20}, "pass_through": 1.0})
    assert set(r["price_changes"]) == {"ribeye"}
    rib = r["items"]["ribeye"]
    # full pass-through at 20% on a 0.625 lb steak recovers the dollar cost increase
    old = rib["baseline"]["unit_cost"]
    assert r["items"]["ribeye"]["price_test"]["p1"] - rib["baseline"]["price"] == pytest.approx(
        rib["by_band"]["medium"]["ingredient_cost"] / rib["by_band"]["medium"]["units"] - old
    )


def test_elasticity_override_collapses_the_range(base):
    r = run_scenario(base, {"price_change": {"ribeye": 0.05}, "elasticity_override": {"ribeye": -1.3}, "substitution": 0.0})
    ch = {r["items"]["ribeye"]["by_band"][b]["profit_change"] for b in ("low", "medium", "high")}
    assert len(ch) == 1


def test_matrix_thresholds_both_returned(base):
    r = run_scenario(base, {"cost_shock": {i: 0.30 for i in BEEF}})
    assert r["matrix"]["baseline_thresholds"]["Entrees"]["margin_threshold"] != r["matrix"]["scenario_thresholds"]["Entrees"]["margin_threshold"]
    moved = [i for i, v in r["items"].items() if v["matrix"]["moved"]]
    assert moved, "a 30% beef shock should move at least one item"


def test_ground_truth_never_needed(base):
    assert "ground_truth" not in str(base.keys())
