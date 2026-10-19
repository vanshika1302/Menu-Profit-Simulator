import json
import math
from pathlib import Path

import pytest

from scripts.run_validation import compute
from sim import model
from sim.validation import band_hit_rate, naive_history_estimates, true_profit_changes

ROOT = Path(__file__).resolve().parents[1]


def test_band_hit_rate_hand_computed():
    truth = {
        "a": {"category": "X", "true_elasticity": -1.0},
        "b": {"category": "X", "true_elasticity": -0.4},   # less elastic than the low band
        "c": {"category": "Y", "true_elasticity": -2.0},   # more elastic than the high band
        "d": {"category": "Y", "true_elasticity": -1.8},   # on the edge counts inside
    }
    r = band_hit_rate(truth)
    assert r["inside_band"] == 2 and r["rate"] == 0.5
    assert r["by_category"] == {"X": {"inside": 1, "of": 2}, "Y": {"inside": 1, "of": 2}}


def test_true_process_matches_model_when_truth_equals_assumptions():
    items = [
        {"item_id": "a", "category": "X", "price": 15.0, "units": 100.0},
        {"item_id": "b", "category": "X", "price": 12.0, "units": 60.0},
        {"item_id": "c", "category": "Y", "price": 9.0, "units": 40.0},
    ]
    costs = {"a": 5.0, "b": 4.0, "c": 3.0}
    truth = {i["item_id"]: {"true_elasticity": -1.2, "within": 0.3, "cross": 0.0} for i in items}
    got = true_profit_changes(items, costs, {"a": 0.1}, truth)
    recipes = {k: {"x": v} for k, v in costs.items()}
    sim = model.simulate(items, recipes, {"x": 1.0}, {"a": 0.1}, elasticity=-1.2, substitution=0.3)
    assert got["total"] == pytest.approx(sim["total"]["profit_change"])
    assert got["own"]["a"] == pytest.approx(sim["items"]["a"]["profit_change"])


def test_cross_category_switching_moves_other_categories():
    items = [
        {"item_id": "a", "category": "X", "price": 15.0, "units": 100.0},
        {"item_id": "b", "category": "Y", "price": 12.0, "units": 60.0},
    ]
    costs = {"a": 5.0, "b": 4.0}
    base = {i["item_id"]: {"true_elasticity": -1.0, "within": 0.0, "cross": 0.0} for i in items}
    cross = {**base, "a": {"true_elasticity": -1.0, "within": 0.0, "cross": 0.5}}
    assert true_profit_changes(items, costs, {"a": 0.1}, cross)["total"] > true_profit_changes(items, costs, {"a": 0.1}, base)["total"]


def _sales(item, prices, units):
    return [{"week_start": w, "item_id": item, "units_sold": u, "avg_selling_price": p}
            for w, (p, u) in enumerate(zip(prices, units))]


def test_naive_history_recovers_clean_elasticity():
    # price 10 -> 11, units fall exactly by 1.1**-1.5 with no noise
    units = [100] * 8 + [100 * 1.1**-1.5] * 8
    sales = _sales("a", [10.0] * 8 + [11.0] * 8, units)
    r = naive_history_estimates(sales, {"a": {"true_elasticity": -1.5}})
    assert r["events"] == 1
    assert r["detail"][0]["naive"] == pytest.approx(-1.5)
    assert r["median_abs_error"] == pytest.approx(0.0, abs=1e-9)


def test_naive_history_is_fooled_by_a_trend():
    units = [100 + 5 * w for w in range(16)]  # demand grows by itself
    sales = _sales("a", [10.0] * 8 + [11.0] * 8, units)
    r = naive_history_estimates(sales, {"a": {"true_elasticity": -1.5}})
    assert r["detail"][0]["naive"] > 0 and r["wrong_sign_share"] == 1.0


def _close(a, b, rel=1e-6):
    if isinstance(a, dict):
        assert a.keys() == b.keys()
        for k in a:
            _close(a[k], b[k], rel)
    elif isinstance(a, list):
        assert len(a) == len(b)
        for x, y in zip(a, b):
            _close(x, y, rel)
    elif isinstance(a, float) or isinstance(b, float):
        assert a == pytest.approx(b, rel=rel, abs=1e-9)
    else:
        assert a == b


def test_snapshot_matches_committed_results():
    """No bounds on the findings; any change in them must be noticed and re-recorded on purpose
    (python scripts/run_validation.py)."""
    committed = json.loads((ROOT / "validation_results.json").read_text())
    _close(json.loads(json.dumps(compute())), committed)
