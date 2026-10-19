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
