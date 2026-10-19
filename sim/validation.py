"""Ground-truth scorecard. The ONLY module allowed to read ground truth.

Everything here compares the simulator with the authored truth in
data/synthetic/ground_truth.csv. The truth is authored, not empirical, so these
numbers show where the method works and where it fails on synthetic data, not
real-world accuracy. There are no pass/fail bounds on any finding.

Functions take plain data; only `load_ground_truth` touches the file.
"""
from __future__ import annotations

import csv
import math
import statistics
from pathlib import Path
from typing import Mapping

import numpy as np

from sim import model
from sim.scenarios import DEFAULT_BANDS, run_scenario

ROOT = Path(__file__).resolve().parents[1]
GROUND_TRUTH_CSV = ROOT / "data" / "synthetic" / "ground_truth.csv"
STANDARD_STEPS = (0.05, 0.10)


def load_ground_truth(path: Path = GROUND_TRUTH_CSV) -> dict[str, dict]:
    with open(path, newline="") as f:
        return {
            r["item_id"]: {
                "category": r["category"],
                "true_elasticity": float(r["true_elasticity"]),
                "within": float(r["within_category_switch_share"]),
                "cross": float(r["cross_category_switch_share"]),
            }
            for r in csv.DictReader(f)
        }


def band_hit_rate(truth: Mapping[str, dict], bands: Mapping[str, float] = DEFAULT_BANDS) -> dict:
    lo, hi = min(bands.values()), max(bands.values())
    hits = {i: lo <= t["true_elasticity"] <= hi for i, t in truth.items()}
    by_cat: dict[str, list[bool]] = {}
    for i, t in truth.items():
        by_cat.setdefault(t["category"], []).append(hits[i])
    return {
        "items": len(hits),
        "inside_band": sum(hits.values()),
        "rate": sum(hits.values()) / len(hits),
        "by_category": {c: {"inside": sum(v), "of": len(v)} for c, v in sorted(by_cat.items())},
    }


def true_profit_changes(
    items: list[dict], costs: Mapping[str, float], price_change: Mapping[str, float], truth: Mapping[str, dict]
) -> dict:
    """Profit change under the true demand process, mirroring the generator: own demand at the
    true elasticity, then the true within-category and cross-category switching."""
    own, inflow = {}, {i["item_id"]: 0.0 for i in items}
    for it in items:
        i = it["item_id"]
        own[i] = model.demand(it["units"], 1 + price_change.get(i, 0.0), truth[i]["true_elasticity"])
    for j in items:
        lost = j["units"] - own[j["item_id"]]
        if lost == 0:
            continue
        t = truth[j["item_id"]]
        same = [k for k in items if k["category"] == j["category"] and k["item_id"] != j["item_id"]]
        other = [k for k in items if k["category"] != j["category"]]
        for group, share in ((same, t["within"]), (other, t["cross"])):
            pop = sum(k["units"] for k in group)
            for k in group:
                inflow[k["item_id"]] += share * lost * k["units"] / pop if pop else 0.0
    own_change, total = {}, 0.0
    for it in items:
        i = it["item_id"]
        p1 = it["price"] * (1 + price_change.get(i, 0.0))
        units1 = max(0.0, own[i] + inflow[i])
        total += (p1 - costs[i]) * units1 - (it["price"] - costs[i]) * it["units"]
        own_change[i] = (p1 - costs[i]) * own[i] - (it["price"] - costs[i]) * it["units"]
    return {"total": total, "own": own_change}


def scenario_scorecard(baseline: Mapping, truth: Mapping[str, dict], steps=STANDARD_STEPS) -> dict:
    """Run +5% and +10% on each item (one at a time) and compare with the truth."""
    costs = model.unit_costs(baseline["recipes"], baseline["ingredient_costs"])
    cover, verdict_rows = [], []
    for it in baseline["items"]:
        i = it["item_id"]
        for step in steps:
            res = run_scenario(baseline, {"price_change": {i: step}})
            rng = res["total"]["profit_change_range"]
            tr = true_profit_changes(baseline["items"], costs, {i: step}, truth)
            cover.append({"item": i, "category": it["category"], "step": step,
                          "inside": rng["low"] <= tr["total"] <= rng["high"],
                          "above": tr["total"] > rng["high"], "below": tr["total"] < rng["low"]})
            v = res["items"][i]["price_test"]["verdict"]
            kind = "pays" if v == "pays off under all bands" else "loses" if v == "loses money under all bands" else "depends"
            med = res["items"][i]["price_test"]["by_band"]["medium"]["own_profit_change"] > 0
            verdict_rows.append({"item": i, "step": step, "kind": kind, "truth_pays": tr["own"][i] > 0, "medium_pays": med})

    def rate(rows, key="inside"):
        return sum(r[key] for r in rows) / len(rows) if rows else None

    by_cat: dict[str, list] = {}
    for r in cover:
        by_cat.setdefault(r["category"], []).append(r)
    decisive = [r for r in verdict_rows if r["kind"] != "depends"]
    right = [r for r in decisive if (r["kind"] == "pays") == r["truth_pays"]]
    wrong_pays = [r for r in verdict_rows if r["kind"] == "pays" and not r["truth_pays"]]
    wrong_loses = [r for r in verdict_rows if r["kind"] == "loses" and r["truth_pays"]]
    return {
        "scenarios": len(cover),
        "profit_range_coverage": {
            "rate": rate(cover),
            "truth_above_range": rate(cover, "above"),
            "truth_below_range": rate(cover, "below"),
            "by_category": {c: rate(v) for c, v in sorted(by_cat.items())},
        },
        "verdicts": {
            "total": len(verdict_rows),
            "pays_off_under_all_bands": sum(r["kind"] == "pays" for r in verdict_rows),
            "loses_under_all_bands": sum(r["kind"] == "loses" for r in verdict_rows),
            "depends_on_elasticity": sum(r["kind"] == "depends" for r in verdict_rows),
            "decisive_accuracy": len(right) / len(decisive) if decisive else None,
            "costly_errors_pays_when_truth_loses": len(wrong_pays),
            "missed_wins_loses_when_truth_pays": len(wrong_loses),
            "medium_band_sign_accuracy": sum(r["medium_pays"] == r["truth_pays"] for r in verdict_rows) / len(verdict_rows),
            "medium_band_says_pays_when_truth_loses": sum(r["medium_pays"] and not r["truth_pays"] for r in verdict_rows),
            "medium_band_says_loses_when_truth_pays": sum((not r["medium_pays"]) and r["truth_pays"] for r in verdict_rows),
            "truth_pays_share": sum(r["truth_pays"] for r in verdict_rows) / len(verdict_rows),
        },
    }


def naive_history_estimates(sales: list[dict], truth: Mapping[str, dict], window: int = 8) -> dict:
    """Before/after arc elasticity at every price change in the history, with its error.

    `sales` rows: {"week_start", "item_id", "units_sold", "avg_selling_price"}. The "after"
    window runs until the next price change (at most `window` weeks); the "before" window is
    the constant-price stretch before the change (at most `window` weeks).
    """
    by_item: dict[str, list[dict]] = {}
    for r in sales:
        by_item.setdefault(r["item_id"], []).append(r)
    events = []
    for item, rows in sorted(by_item.items()):
        rows = sorted(rows, key=lambda r: r["week_start"])
        price = [r["avg_selling_price"] for r in rows]
        units = [r["units_sold"] for r in rows]
        cuts = [w for w in range(1, len(rows)) if price[w] != price[w - 1]]
        for w in cuts:
            a_end = next((c for c in cuts if c > w), len(rows))
            a = range(w, min(w + window, a_end))
            b_start = max([c for c in cuts if c < w] + [0])
            b = range(max(w - window, b_start), w)
            if len(a) < 1 or len(b) < 1:
                continue
            u_a, u_b = statistics.mean(units[k] for k in a), statistics.mean(units[k] for k in b)
            p_a, p_b = statistics.mean(price[k] for k in a), statistics.mean(price[k] for k in b)
            if u_a <= 0 or u_b <= 0:
                continue
            naive = math.log(u_a / u_b) / math.log(p_a / p_b)
            events.append({
                "item": item, "week": w, "price_change_pct": (p_a / p_b - 1) * 100,
                "naive": naive, "true": truth[item]["true_elasticity"],
                "error": naive - truth[item]["true_elasticity"],
            })
    errs = [abs(e["error"]) for e in events]
    lo, hi = min(DEFAULT_BANDS.values()), max(DEFAULT_BANDS.values())
    return {
        "events": len(events),
        "median_abs_error": statistics.median(errs) if errs else None,
        "mean_abs_error": statistics.mean(errs) if errs else None,
        "wrong_sign_share": sum(e["naive"] > 0 for e in events) / len(events) if events else None,
        "outside_band_share": sum(not (lo <= e["naive"] <= hi) for e in events) / len(events) if events else None,
        "detail": events,  # per-item truth: validation use only, never the dashboard
    }


def run_scorecard(baseline: Mapping, truth: Mapping[str, dict], sales: list[dict]) -> dict:
    return {
        "note": "Synthetic data and authored ground truth: shows where the method works and fails, not real-world accuracy.",
        "bands": dict(DEFAULT_BANDS),
        "band_hit_rate": band_hit_rate(truth),
        "scenario_scorecard": scenario_scorecard(baseline, truth),
        "naive_history": naive_history_estimates(sales, truth),
    }


# ---------------------------------------------------------------------------
# Experiment-recovery Monte Carlo (slow; run with scripts/run_validation.py --full)
# ---------------------------------------------------------------------------

RECOVERY_REPS = 200
RECOVERY_SEED = 42


def simulate_switchback(
    rng, base_daily: float, ratio: float, eps_true: float, weeks: int, eps_star: float, rise: bool, n_perm: int = 199
) -> dict:
    """One simulated switchback test on one item: one-day blocks, whole weeks, random arms.

    Only clean blocks (same arm as the previous day) are analysed, matching the design's
    carryover assumption. Returns the measured elasticity, the roll-out decision, and a
    randomization-test p-value for a difference in units between arms.
    """
    from etl.generate import counterfactual_daily_units  # generator-owned truth

    days = 7 * weeks
    arm = rng.integers(0, 2, size=days)
    r_today = np.where(arm == 1, ratio, 1.0)
    r_prev = np.concatenate([[1.0], r_today[:-1]])
    units = counterfactual_daily_units(rng, base_daily, r_today, r_prev, eps_true)
    clean = np.concatenate([[False], arm[1:] == arm[:-1]])
    t, c = units[clean & (arm == 1)], units[clean & (arm == 0)]
    if len(t) < 2 or len(c) < 2 or c.mean() == 0 or t.mean() == 0:
        return {"eps_hat": None, "roll_out": None, "p_value": None}
    eps_hat = math.log(t.mean() / c.mean()) / math.log(ratio)
    obs = abs(t.mean() - c.mean())
    pool, labels = units[clean], arm[clean]
    exceed = 0
    for _ in range(n_perm):
        perm = rng.permutation(labels)
        exceed += abs(pool[perm == 1].mean() - pool[perm == 0].mean()) >= obs
    return {
        "eps_hat": eps_hat,
        "roll_out": eps_hat > eps_star if rise else eps_hat < eps_star,
        "p_value": (exceed + 1) / (n_perm + 1),
    }


def experiment_recovery(baseline: Mapping, truth: Mapping[str, dict], entries: list[dict],
                        reps: int = RECOVERY_REPS, seed: int = RECOVERY_SEED, cap_weeks: int = 12) -> dict:
    """For each backlog price entry, run `reps` simulated tests at the planned duration and at the cap.

    Decision accuracy = share of replications whose roll-out decision matches the truth
    (true elasticity above the break-even elasticity for a rise, below for a cut).
    """
    items = {i["item_id"]: i for i in baseline["items"]}
    out = []
    for k, e in enumerate(entries):
        it = items[e["target"]]
        eps_star, rise = e["break_even_elasticity"], e["price_rise"]
        eps_true = truth[it["item_id"]]["true_elasticity"]
        truth_roll_out = eps_true > eps_star if rise else eps_true < eps_star
        row = {"item": it["item_id"], "rank": e["rank"], "break_even_elasticity": eps_star,
               "truth_says_roll_out": truth_roll_out, "planned_weeks": e["duration_weeks"], "runs": {}}
        for label, weeks in (("planned_duration", e["duration_weeks"]), ("at_cap", cap_weeks)):
            rng = np.random.default_rng(seed + 1000 * k + (0 if label == "at_cap" else 1))
            sims = [simulate_switchback(rng, it["units"] / 7, e["ratio"], eps_true, weeks, eps_star, rise)
                    for _ in range(reps)]
            sims = [s for s in sims if s["eps_hat"] is not None]
            est = np.array([s["eps_hat"] for s in sims])
            lo, hi = np.percentile(est, [5, 95])
            row["runs"][label] = {
                "weeks": weeks,
                "decision_accuracy": float(np.mean([s["roll_out"] == truth_roll_out for s in sims])),
                "estimate_interval_90": [float(lo), float(hi)],
                "estimate_interval_width": float(hi - lo),
                "estimate_mean_error": float(est.mean() - eps_true),
                "conclusive_share": float(np.mean([s["p_value"] < 0.05 for s in sims])),
            }
        out.append(row)
    accs = {lab: float(np.mean([r["runs"][lab]["decision_accuracy"] for r in out])) for lab in ("planned_duration", "at_cap")}
    return {"reps": reps, "seed": seed, "entries": out, "mean_decision_accuracy": accs,
            "note": "Top price-switchback entries; weak-evidence entries have no elasticity decision to recover."}
