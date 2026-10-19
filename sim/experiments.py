"""Ranked experiment backlog: candidates, score, duration, guardrails, stop rules.

Pure functions over plain data. Inputs are a baseline (sim/scenarios.py shape, plus
"weekly_units_history": {item_id: [weekly units over the window]}) and the result of
run_scenario().

score = stake x decision_uncertainty x feasibility / (1 + normalised_risk)

  stake                 largest annualized profit change across the bands (own profit)
  decision_uncertainty  4p(1-p), p = share of the elasticity band on the losing side of
                        the break-even elasticity; 0 when the whole band agrees, 1 when
                        it splits evenly
  feasibility           0..1 from the duration; over the cap it is near 0 (never hidden) and the entry goes on the "needs pooling" list
  normalised_risk       profit at risk during the test (worst band, exposed share of the
                        week) as a share of the target's weekly profit, so item size does
                        not cancel out of the score

Design assumptions (all labelled assumed in each entry):
  - one-day blocks, whole weeks, randomised assignment
  - carryover m = 1 block: only the blocks whose previous block had the same arm are
    clean, a fraction 2**-m, so usable blocks = total blocks x 2**-m
  - n = 32 sigma^2 / delta^2 clean blocks per arm (95% confidence, 90% power)
  - sigma_block = sd of weekly profit over the baseline window / sqrt(7) (days independent;
    the window includes any seasonal drift, so this errs high)
  - delta (the effect to resolve) = the gap between the low-band and high-band profit
    change, per block: the test has to tell the ends of the assumed band apart
"""
from __future__ import annotations

import math
import statistics
from typing import Mapping

from sim import model, scenarios

CAP_WEEKS = 12
CARRYOVER_M = 1
MIN_WEEKS = 2  # one full week of each arm before a harm stop can fire, then a second look
EXPOSED_SHARE = 0.5  # half of the blocks get the treatment arm
FEASIBILITY_OVER_CAP = 0.02
DEFAULT_PRICE_STEP = 0.05  # small default price rise for Plowhorse and Dog items not in the scenario

# Weak-evidence tests (portion, menu design). No effect sizes are taken from the literature.
# Stake and risk are sized from the project's own numbers and labelled illustrative:
#   portion test: 10% smaller portion cuts ingredient cost by 10% (arithmetic from the recipe),
#                 volume held; stake = that saving over a year.
#   menu-design test: the profit value of a 5% volume lift on the item (what the effect would be
#                 worth, not a claim that it happens); stake = that over a year.
#   risk (both): a 5% volume loss on the exposed share of the week.
#   decision uncertainty is 1.0: no evidence supports any prior on the effect, so it is treated
#                 as maximally uncertain, which is stated in the entry.
PORTION_CUT = 0.10
DESIGN_LIFT = 0.05
WEAK_VOLUME_LOSS = 0.05

GUARDRAILS = {
    "metrics": [
        {"name": "Total units sold (traffic proxy)", "stop_if_down_pct": 3.0},
        {"name": "Menu-total contribution profit per week", "stop_if_down_pct": 2.0},
        {"name": "Same-category units (cannibalization)", "stop_if_down_pct": None},
    ],
    "label": "policy choice, not evidence",
}
STOP_RULES = {
    "harm": "Stop if a guardrail is beyond its threshold at two consecutive weekly looks, after at least one full week of each arm.",
    "cap": "Stop at the planned duration or the 12-week cap, whichever comes first.",
    "success": "No early success stop. Read the result only at the planned end with the design-matched randomization test.",
}


def decision_uncertainty(p: float) -> float:
    return 4 * p * (1 - p)


def share_losing(rise: bool, eps_star: float, band_low: float, band_high: float) -> float:
    """Share of the band [band_high, band_low] (e.g. -1.8 to -0.5) on the losing side of eps*."""
    f = min(1.0, max(0.0, (eps_star - band_high) / (band_low - band_high)))
    return f if rise else 1 - f


def sigma_block(units_history: list[float], cm: float) -> float:
    """sd of weekly contribution profit / sqrt(7). Assumed: days independent."""
    if len(units_history) < 2:
        return 0.0
    return statistics.stdev(units_history) * abs(cm) / math.sqrt(7)


def duration_weeks(sigma: float, delta: float, m: int = CARRYOVER_M) -> int | None:
    """Whole weeks needed; None if delta is zero."""
    if delta <= 0:
        return None
    n_clean = 32 * sigma**2 / delta**2
    blocks = 2 * n_clean / 2**-m
    return max(MIN_WEEKS, math.ceil(blocks / 7))


def feasibility(weeks: int | None, cap: int = CAP_WEEKS) -> float:
    """1 - weeks / (2 x cap) within the cap (0.5 to 1). Over the cap it is at most
    FEASIBILITY_OVER_CAP, shrinking as cap / weeks, so the "needs pooling" list is ordered
    by how close each test is to feasible rather than tied."""
    if weeks is None:
        return 0.0
    if weeks > cap:
        return FEASIBILITY_OVER_CAP * cap / weeks
    return 1 - weeks / (2 * cap)


def score(stake: float, uncertainty: float, feas: float, risk_norm: float) -> float:
    return stake * uncertainty * feas / (1 + risk_norm)


def _entry(*, target, target_name, etype, evidence, stake, unc, risk_norm, sigma, delta, weekly_profit,
           hypothesis, decision, assumptions, cap, m):
    weeks = duration_weeks(sigma, delta, m)
    feas = feasibility(weeks, cap)
    ok = weeks is not None and weeks <= cap
    return {
        "target": target,
        "target_name": target_name,
        "type": etype,
        "evidence": evidence,
        "score": score(stake, unc, feas, risk_norm),
        "factors": {"stake": stake, "decision_uncertainty": unc, "feasibility": feas, "normalised_risk": risk_norm},
        "hypothesis": hypothesis,
        "design": {
            "arms": ["control", "treatment"],
            "block": "one day",
            "assignment": "randomized by day, whole weeks only",
            "carryover_blocks": m,
            "clean_block_share": 2**-m,
        },
        "duration_weeks": weeks,
        "feasible_alone": ok,
        "feasibility_note": None if ok else "Not feasible alone: pool the category or accept a larger detectable effect.",
        "primary_metric": "Contribution profit per day for the target",
        "mde": {"per_block": delta, "pct_of_block_profit": delta / (weekly_profit / 7) if weekly_profit else None},
        "guardrails": GUARDRAILS,
        "stop_rules": STOP_RULES,
        "decision_rule": decision,
        "assumptions": {k: {"value": v, "label": "assumed"} for k, v in assumptions.items()},
    }


def _price_entry(it, test, weekly_profit, sigma, band_low, band_high, cap, m, assumptions):
    rise = test["p1"] > test["p0"]
    eps = test["break_even_elasticity"]
    changes = [b["own_profit_change"] for b in test["by_band"].values()]
    p = share_losing(rise, eps, band_low, band_high)
    pct = abs(test["p1"] / test["p0"] - 1) * 100
    risk = max(0.0, -min(changes)) * EXPOSED_SHARE
    delta = (max(changes) - min(changes)) / 7
    name = it.get("name") or it["item_id"]
    return _entry(
        target=it["item_id"], target_name=name, etype="Price switchback test", evidence="method-backed",
        stake=max(abs(c) for c in changes) * model.WEEKS_PER_YEAR,
        unc=decision_uncertainty(p), risk_norm=risk / weekly_profit if weekly_profit else 0.0,
        sigma=sigma, delta=delta, weekly_profit=weekly_profit,
        hypothesis=(
            f"Demand for {name} is {'less' if rise else 'more'} elastic than {eps:.2f}, "
            f"so a {'+' if rise else '-'}{pct:.0f}% price change raises profit."
        ),
        decision=(
            f"If the measured elasticity is {'above' if rise else 'below'} {eps:.2f}, roll out the change; otherwise revert."
        ),
        assumptions=assumptions, cap=cap, m=m,
    )


def build_backlog(baseline: Mapping, result: Mapping, params: Mapping | None = None) -> dict:
    """Return {"feasible_now": [...], "needs_pooling": [...], "all": [...]} with ranks.

    params: cap_weeks, carryover_m, default_price_step.
    """
    params = params or {}
    cap = params.get("cap_weeks", CAP_WEEKS)
    m = params.get("carryover_m", CARRYOVER_M)
    step = params.get("default_price_step", DEFAULT_PRICE_STEP)
    bands = result["bands"]
    band_low, band_high = max(bands.values()), min(bands.values())
    history = baseline.get("weekly_units_history", {})
    items = {i["item_id"]: i for i in baseline["items"]}
    costs = model.unit_costs(baseline["recipes"], baseline["ingredient_costs"])
    new_costs = {
        i: row["by_band"]["medium"]["ingredient_cost"] / row["by_band"]["medium"]["units"] if row["by_band"]["medium"]["units"] else costs[i]
        for i, row in result["items"].items()
    }

    entries: list[dict] = []
    scenario_tests: dict[str, dict] = {}
    for i, row in result["items"].items():
        it = items[i]
        base = row["baseline"]
        weekly_profit = base["profit"]
        sigma = sigma_block(history.get(i, []), base["cm"])
        assumptions = {
            "elasticity_band": [band_high, band_low], "sigma_per_day": sigma, "carryover_blocks": m,
            "cap_weeks": cap, "substitution_share": result["substitution"],
        }
        test = row["price_test"]
        cls = row["matrix"]["baseline_class"]
        if test is not None and test["break_even_elasticity"] is not None:
            scenario_tests[i] = test
            entries.append(_price_entry(it, test, weekly_profit, sigma, band_low, band_high, cap, m, assumptions))
        elif test is None and cls in ("Plowhorse", "Dog"):
            # default small price rise, evaluated with the same machinery
            eff = {b: e for b, e in bands.items()}
            t = scenarios.price_test(it, it["price"] * (1 + step), new_costs[i], eff, result["substitution"],
                                     baseline["items"], new_costs)
            if t["break_even_elasticity"] is not None:
                entries.append(_price_entry(it, t, weekly_profit, sigma, band_low, band_high, cap, m, assumptions))
        # weak-evidence candidates from the item's class
        name = it.get("name") or i
        if cls in ("Plowhorse", "Dog"):
            saving = PORTION_CUT * costs[i] * it["units"]
            loss = WEAK_VOLUME_LOSS * weekly_profit * EXPOSED_SHARE
            entries.append(_entry(
                target=i, target_name=name, etype="Portion test", evidence="weak prior",
                stake=saving * model.WEEKS_PER_YEAR, unc=1.0, risk_norm=loss / weekly_profit if weekly_profit else 0.0,
                sigma=sigma, delta=saving / 7, weekly_profit=weekly_profit,
                hypothesis=f"A {PORTION_CUT:.0%} smaller portion of {name} raises profit per unit without losing buyers. Effect unknown: test to measure it.",
                decision="If volume holds within the guardrails, keep the smaller portion; otherwise revert.",
                assumptions={**assumptions, "illustrative_portion_cut": PORTION_CUT, "illustrative_volume_loss": WEAK_VOLUME_LOSS,
                             "decision_uncertainty": "1.0 by construction: no evidence supports a prior"},
                cap=cap, m=m))
        if cls == "Puzzle":
            gain = DESIGN_LIFT * weekly_profit
            loss = WEAK_VOLUME_LOSS * weekly_profit * EXPOSED_SHARE
            entries.append(_entry(
                target=i, target_name=name, etype="Menu-design test", evidence="weak prior",
                stake=gain * model.WEEKS_PER_YEAR, unc=1.0, risk_norm=loss / weekly_profit if weekly_profit else 0.0,
                sigma=sigma, delta=gain / 7, weekly_profit=weekly_profit,
                hypothesis=f"A clearer label, description or position lifts volume of {name}. Effect unknown: test to measure it.",
                decision="If the lift is positive and the guardrails hold, keep the new design; otherwise revert.",
                assumptions={**assumptions, "illustrative_volume_lift": DESIGN_LIFT, "illustrative_volume_loss": WEAK_VOLUME_LOSS,
                             "decision_uncertainty": "1.0 by construction: no evidence supports a prior"},
                cap=cap, m=m))

    # category-pooled price tests where the scenario changes two or more items in a category
    by_cat: dict[str, list[str]] = {}
    for i in scenario_tests:
        by_cat.setdefault(items[i].get("category"), []).append(i)
    for cat, ids in by_cat.items():
        if len(ids) < 2:
            continue
        entries.append(_pooled_price_entry(cat, ids, scenario_tests, result, baseline, items, history, band_low, band_high,
                                           cap, m))

    return _rank(entries)


def _pooled_price_entry(cat, ids, tests, result, baseline, items, history, band_low, band_high, cap, m):
    band_names = list(result["bands"])
    pooled = [sum(tests[i]["by_band"][b]["own_profit_change"] for i in ids) for b in band_names]
    # share of the band where the pooled change is negative, on a fine grid
    grid = [band_high + (band_low - band_high) * k / 100 for k in range(101)]

    def pooled_change(eps):
        return sum(
            (tests[i]["p1"] - tests[i]["unit_cost"]) * items[i]["units"] * (tests[i]["p1"] / tests[i]["p0"]) ** eps
            - (tests[i]["p0"] - tests[i]["unit_cost"]) * items[i]["units"]
            for i in ids
        )

    p = sum(1 for e in grid if pooled_change(e) < 0) / len(grid)
    weekly_profit = sum(result["items"][i]["baseline"]["profit"] for i in ids)
    var = sum(sigma_block(history.get(i, []), result["items"][i]["baseline"]["cm"]) ** 2 for i in ids)
    sigma = math.sqrt(var)
    risk = max(0.0, -min(pooled)) * EXPOSED_SHARE
    delta = (max(pooled) - min(pooled)) / 7
    names = ", ".join(items[i].get("name") or i for i in ids)
    return _entry(
        target=cat, target_name=f"{cat} (pooled: {names})", etype="Price switchback test (category pooled)",
        evidence="method-backed", stake=max(abs(c) for c in pooled) * model.WEEKS_PER_YEAR,
        unc=decision_uncertainty(p), risk_norm=risk / weekly_profit if weekly_profit else 0.0,
        sigma=sigma, delta=delta, weekly_profit=weekly_profit,
        hypothesis=f"The combined price changes on {names} raise category contribution profit.",
        decision="If measured category profit per day rises beyond the guardrails' tolerance, roll out all the changes; otherwise revert.",
        assumptions={"elasticity_band": [band_high, band_low], "sigma_per_day": sigma, "carryover_blocks": m,
                     "cap_weeks": cap, "pooling": "item sigmas combined as independent"},
        cap=cap, m=m,
    )


def _rank(entries: list[dict]) -> dict:
    feasible = sorted((e for e in entries if e["feasible_alone"]), key=lambda e: -e["score"])
    needs = sorted((e for e in entries if not e["feasible_alone"]), key=lambda e: -e["score"])
    for lst in (feasible, needs):
        for r, e in enumerate(lst, 1):
            e["rank"] = r
    return {"feasible_now": feasible, "needs_pooling": needs, "all": feasible + needs}
