import math

import pytest

from etl.baseline import baseline_from_warehouse
from etl.load import load_all
from etl.warehouse import get_connection
from sim.experiments import (
    CAP_WEEKS,
    build_backlog,
    decision_uncertainty,
    duration_weeks,
    feasibility,
    score,
    share_losing,
    sigma_block,
)
from sim.scenarios import run_scenario


@pytest.fixture(scope="module")
def base():
    con = get_connection(":memory:")
    load_all(con)
    b = baseline_from_warehouse(con)
    con.close()
    return b


def test_decision_uncertainty_bounds():
    # rise, band -1.8..-0.5. eps* below the band (-3): every elasticity in the band pays off
    assert decision_uncertainty(share_losing(True, -3.0, -0.5, -1.8)) == 0
    # eps* above the band (0): every elasticity loses
    assert decision_uncertainty(share_losing(True, 0.0, -0.5, -1.8)) == 0
    # eps* at the band midpoint splits it evenly
    assert decision_uncertainty(share_losing(True, -1.15, -0.5, -1.8)) == pytest.approx(1.0)
    # a cut mirrors it
    assert share_losing(False, -1.15, -0.5, -1.8) == pytest.approx(0.5)
    assert share_losing(False, -3.0, -0.5, -1.8) == pytest.approx(1.0)


def test_score_monotonic():
    base_args = dict(stake=1000, uncertainty=0.5, feas=0.5, risk_norm=0.1)
    s0 = score(**base_args)
    assert score(**{**base_args, "stake": 2000}) > s0
    assert score(**{**base_args, "feas": 0.9}) > s0
    assert score(**{**base_args, "uncertainty": 0.9}) > s0
    assert score(**{**base_args, "risk_norm": 0.5}) < s0


def test_feasibility_monotonic_and_over_cap():
    vals = [feasibility(w) for w in range(2, CAP_WEEKS + 1)]
    assert vals == sorted(vals, reverse=True) and vals[0] <= 1 and vals[-1] >= 0.5
    over = [feasibility(w) for w in (13, 26, 100)]
    assert over == sorted(over, reverse=True)
    assert all(0 < v <= 0.02 for v in over)
    assert feasibility(None) == 0.0


def test_duration_hand_computed():
    # sigma 10, delta 5: n = 32 x 100 / 25 = 128 clean blocks per arm
    # two arms, clean share 1/2: 512 blocks = 73.14 weeks -> 74
    assert duration_weeks(10, 5, m=1) == math.ceil(512 / 7)
    assert duration_weeks(10, 5, m=0) == math.ceil(256 / 7)
    assert duration_weeks(1, 1000) == 2  # never under two weeks
    assert duration_weeks(10, 0) is None


def test_sigma_block():
    # differences of [100, 120, 80, 100] are 20, -40, 20: sd 34.641; / sqrt(2) / sqrt(7) x |cm|
    assert sigma_block([100, 120, 80, 100], 10) == pytest.approx(10 * 34.641016 / math.sqrt(2) / math.sqrt(7), rel=1e-6)
    assert sigma_block([100, 120], 10) == 0


def test_sigma_ignores_a_smooth_trend():
    flat_noise = [100, 104, 98, 102, 99, 103]
    drifting = [x + 10 * i for i, x in enumerate(flat_noise)]
    # a linear drift adds a constant to every first difference: the spread is unchanged
    assert sigma_block(drifting, 5) == pytest.approx(sigma_block(flat_noise, 5))


def test_risk_is_normalised_by_item_size(base):
    """Doubling an item's volume doubles its stake but leaves its normalised risk unchanged."""
    scen = {"price_change": {"ribeye": 0.05}, "bands": {"low": -3.0, "medium": -4.0, "high": -5.0}}

    def entry(b):
        bl = build_backlog(b, run_scenario(b, scen))["all"]
        return next(e for e in bl if e["target"] == "ribeye" and e["type"] == "Price switchback test")

    big = {**base, "items": [{**i, "units": i["units"] * 2} if i["item_id"] == "ribeye" else i for i in base["items"]]}
    small, large = entry(base)["factors"], entry(big)["factors"]
    assert large["stake"] > 1.9 * small["stake"]
    assert large["normalised_risk"] > 0
    assert large["normalised_risk"] == pytest.approx(small["normalised_risk"], rel=0.05)


def test_candidates_follow_class(base):
    r = run_scenario(base, {"price_change": {"ribeye": 0.05}})
    bl = build_backlog(base, r)["all"]
    cls = {i: v["matrix"]["baseline_class"] for i, v in r["items"].items()}
    by_type = lambda t: {e["target"] for e in bl if e["type"] == t}
    assert by_type("Portion test") == {i for i, c in cls.items() if c in ("Plowhorse", "Dog")}
    assert by_type("Menu-design test") == {i for i, c in cls.items() if c == "Puzzle"}
    price = by_type("Price switchback test")
    assert "ribeye" in price                                   # from the scenario
    assert {i for i, c in cls.items() if c in ("Plowhorse", "Dog")} <= price   # default step
    assert not any(cls[i] == "Star" and i in price for i in price if i != "ribeye")  # stars: guardrail only


def test_entry_fields_and_labels(base):
    r = run_scenario(base, {"price_change": {"ribeye": 0.05}})
    e = next(x for x in build_backlog(base, r)["all"] if x["target"] == "ribeye" and x["type"].startswith("Price"))
    for k in ("rank", "score", "factors", "target", "type", "evidence", "hypothesis", "design", "duration_weeks",
              "feasible_alone", "primary_metric", "mde", "guardrails", "stop_rules", "decision_rule", "assumptions"):
        assert k in e
    assert e["evidence"] == "method-backed"
    assert "-1.63" in e["hypothesis"] and "-1.63" in e["decision_rule"]
    assert e["design"]["carryover_blocks"] == 1 and e["design"]["block"] == "one day"
    assert all(v["label"] == "assumed" for v in e["assumptions"].values())
    assert e["guardrails"]["metrics"][0]["stop_if_down_pct"] == 3.0
    assert e["guardrails"]["metrics"][1]["stop_if_down_pct"] == 2.0
    assert "policy choice" in e["guardrails"]["label"]
    weak = next(x for x in build_backlog(base, r)["all"] if x["type"] == "Portion test")
    assert weak["evidence"] == "weak prior" and "Effect unknown" in weak["hypothesis"]
    assert weak["factors"]["decision_uncertainty"] == 1.0


def test_two_lists_ranked(base):
    r = run_scenario(base, {"price_change": {"ribeye": 0.05}})
    wide = build_backlog(base, r, {"cap_weeks": 10**7})
    assert wide["needs_pooling"] == [] and len(wide["feasible_now"]) > 10
    for lst in ("feasible_now", "needs_pooling"):
        entries = build_backlog(base, r)[lst]
        backed = [e["score"] for e in entries if e["evidence"] == "method-backed"]
        weak = [e["score"] for e in entries if e["evidence"] != "method-backed"]
        assert backed == sorted(backed, reverse=True) and weak == sorted(weak, reverse=True)
        kinds = [e["evidence"] == "method-backed" for e in entries]
        assert kinds == sorted(kinds, reverse=True)  # every method-backed entry ahead of every weak one
    all_e = wide["feasible_now"]
    assert [e["rank"] for e in all_e] == list(range(1, len(all_e) + 1))
    assert all(e["feasible_alone"] for e in all_e)
    tight = build_backlog(base, r)
    assert all(not e["feasible_alone"] and e["feasibility_note"] for e in tight["needs_pooling"])


def test_pooled_entry_only_for_two_or_more_scenario_items(base):
    one = build_backlog(base, run_scenario(base, {"price_change": {"ribeye": 0.05}}))["all"]
    assert not any("pooled" in e["type"] for e in one)
    two = build_backlog(base, run_scenario(base, {"price_change": {"ribeye": 0.05, "sirloin": 0.05}}))["all"]
    pooled = [e for e in two if "pooled" in e["type"]]
    assert len(pooled) == 1 and pooled[0]["target"] == "Entrees"


def test_wider_effect_shortens_the_test(base):
    d5 = build_backlog(base, run_scenario(base, {"price_change": {"classic_burger": 0.05}}))["all"]
    d15 = build_backlog(base, run_scenario(base, {"price_change": {"classic_burger": 0.15}}))["all"]
    f = lambda bl: next(e for e in bl if e["target"] == "classic_burger" and e["type"] == "Price switchback test")
    assert f(d15)["duration_weeks"] < f(d5)["duration_weeks"]
