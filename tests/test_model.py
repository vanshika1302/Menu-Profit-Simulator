"""Identity tests and hand-computed examples for sim/model.py."""
import math

import pytest

from sim.model import (
    break_even_drop,
    break_even_drop_net,
    break_even_elasticity,
    destination_cm,
    pass_through_price_change,
    simulate,
    unit_costs,
)

ING = {"beef": 5.0, "bun": 0.5, "cheese": 4.0, "pasta": 1.0, "tomato": 2.0}
RECIPES = {
    "a": {"beef": 1.0, "bun": 1},          # 5.5
    "b": {"beef": 0.5, "cheese": 0.5},     # 4.5
    "c": {"cheese": 0.5},                  # 2.0
    "d": {"pasta": 2.0, "tomato": 1.0},    # 4.0
}
ITEMS = [
    {"item_id": "a", "category": "X", "price": 15.0, "units": 100.0},
    {"item_id": "b", "category": "X", "price": 12.0, "units": 60.0},
    {"item_id": "c", "category": "X", "price": 9.0, "units": 40.0},
    {"item_id": "d", "category": "Y", "price": 14.0, "units": 80.0},
]


def run(**kw):
    return simulate(ITEMS, RECIPES, ING, **kw)


def test_hand_computed_cost():
    c = unit_costs(RECIPES, ING)
    assert c["a"] == pytest.approx(5.5)
    assert c["b"] == pytest.approx(4.5)
    assert c["d"] == pytest.approx(4.0)


def test_hand_computed_price_rise_no_substitution():
    # Item a: P 15 -> 15.75 (+5%), eps -1: units = 100 / 1.05, cm = 15.75 - 5.5 = 10.25
    r = run(price_change={"a": 0.05}, elasticity=-1.0, substitution=0.0)["items"]["a"]
    assert r["units"] == pytest.approx(100 / 1.05)
    assert r["profit"] == pytest.approx(10.25 * 100 / 1.05)
    assert r["baseline"]["profit"] == pytest.approx(950.0)


def test_hand_computed_break_even_elasticity():
    # P0 = 10, c = 4, P1 = 11: ln(6/7) / ln(1.1)
    assert break_even_elasticity(10, 11, 4) == pytest.approx(math.log(6 / 7) / math.log(1.1))
    assert break_even_elasticity(10, 11, 4) == pytest.approx(-1.6173, abs=1e-4)


def test_hand_computed_break_even_drop():
    # CM 6, dP 1: 1 / 7
    assert break_even_drop(10, 11, 4) == pytest.approx(1 / 7)
    # s = 0.5, CM_dest 8: 1 / (6 + 1 - 4) = 1/3
    assert break_even_drop_net(10, 11, 4, 0.5, 8.0) == pytest.approx(1 / 3)


def test_zero_change_returns_baseline():
    res = run()
    assert res["total"]["profit_change"] == pytest.approx(0.0, abs=1e-9)
    for r in res["items"].values():
        assert r["units"] == r["baseline"]["units"]
        assert r["profit"] == pytest.approx(r["baseline"]["profit"])


def test_zero_percent_shock_changes_nothing():
    res = run(cost_shock={"beef": 0.0})
    assert res["total"]["profit_change"] == pytest.approx(0.0, abs=1e-9)


def test_shock_moves_exactly_the_recipes_using_it():
    res = run(cost_shock={"beef": 0.20})["items"]
    for i, recipe in RECIPES.items():
        moved = res[i]["unit_cost"] != pytest.approx(res[i]["baseline"]["unit_cost"])
        assert moved == ("beef" in recipe)
    assert res["a"]["unit_cost"] == pytest.approx(5.5 + 0.2 * 5.0)
    # no price or volume response to a shock by itself
    assert res["a"]["units"] == res["a"]["baseline"]["units"]


def test_profit_unchanged_at_break_even_elasticity():
    p0, c = 15.0, 5.5
    for pct in (0.05, 0.10, -0.08):
        p1 = p0 * (1 + pct)
        eps = break_even_elasticity(p0, p1, c)
        r = run(price_change={"a": pct}, elasticity=eps, substitution=0.0)["items"]["a"]
        assert r["profit_change"] == pytest.approx(0.0, abs=1e-9)


def _drop_to_eps(drop, pct):
    return math.log(1 - drop) / math.log(1 + pct)


def test_break_even_drop_without_substitution():
    pct = 0.10
    drop = break_even_drop(15.0, 15.0 * (1 + pct), 5.5)
    r = run(price_change={"a": pct}, elasticity=_drop_to_eps(drop, pct), substitution=0.0)
    assert r["items"]["a"]["units"] == pytest.approx(100 * (1 - drop))
    assert r["total"]["profit_change"] == pytest.approx(0.0, abs=1e-9)


def test_break_even_drop_net_of_substitution():
    pct, s = 0.10, 0.4
    costs = unit_costs(RECIPES, ING)
    cm_dest = destination_cm(ITEMS, costs, "a")
    drop = break_even_drop_net(15.0, 15.0 * (1 + pct), costs["a"], s, cm_dest)
    r = run(price_change={"a": pct}, elasticity=_drop_to_eps(drop, pct), substitution=s)
    assert r["total"]["profit_change"] == pytest.approx(0.0, abs=1e-9)


def test_net_equals_headline_at_zero_substitution():
    assert break_even_drop_net(15, 16.5, 5.5, 0.0, 7.0) == pytest.approx(break_even_drop(15, 16.5, 5.5))


def test_substitution_conserves_buyers_on_a_rise():
    s, pct = 0.3, 0.10
    r = run(price_change={"a": pct}, elasticity=-1.2, substitution=s)["items"]
    lost = 100 - r["a"]["units"]
    gained = sum(r[i]["units"] - r[i]["baseline"]["units"] for i in ("b", "c"))
    assert gained == pytest.approx(s * lost)
    # destinations split in proportion to baseline popularity (60 : 40)
    assert (r["b"]["units"] - 60) / (r["c"]["units"] - 40) == pytest.approx(60 / 40)
    # other categories are untouched
    assert r["d"]["units"] == 80


def test_price_cut_mirrors_as_cannibalization():
    s, pct = 0.3, -0.10
    r = run(price_change={"a": pct}, elasticity=-1.2, substitution=s)["items"]
    gained = r["a"]["units"] - 100
    assert gained > 0
    taken = 100 - sum(r[i]["units"] for i in ("b", "c"))
    assert taken == pytest.approx(s * gained)
    assert r["d"]["units"] == 80


def test_destination_pays_scenario_price():
    # a rises, b also rises: b's gained buyers are billed at b's new price
    r = run(price_change={"a": 0.10, "b": 0.05}, elasticity=-1.0, substitution=0.5)["items"]
    assert r["b"]["revenue"] == pytest.approx(12.0 * 1.05 * r["b"]["units"])


def test_pass_through():
    assert pass_through_price_change(5.5, 6.5, 15.0, 1.0) == pytest.approx(1.0 / 15.0)
    assert pass_through_price_change(5.5, 6.5, 15.0, 0.5) == pytest.approx(0.5 / 15.0)


def test_break_even_elasticity_undefined_cases():
    assert break_even_elasticity(10, 10, 4) is None
    assert break_even_elasticity(10, 3.5, 4) is None
