"""Scenario engine: one scenario evaluated under each elasticity band.

Pure functions over plain data (see sim/model.py for the shapes). A baseline is

    {"items": [...], "recipes": {...}, "ingredient_costs": {...},
     "window_weeks": 12, "min_units": 50, "popularity_factor": 0.7}

and a scenario is a dict with any of

    cost_shock             {ingredient_id: fraction}
    price_change           {item_id: fraction}
    category_price_change  {category: fraction}      (an item entry wins over its category)
    pass_through           share of a cost increase recovered by price, for items the shock
                           moves and that have no explicit price change
    substitution           share of lost buyers who switch within the category (default 0.25)
    bands                  {"low": -0.5, "medium": -1.0, "high": -1.8}
    elasticity_override    {item_id or category: elasticity}, applied in every band
    scope                  "category" (default) or "menu" for the matrix

Price-change tests (break-even elasticity, break-even drop, verdict) compare the new
price with the old price at the scenario's (post-shock) cost, so a cost shock and a
price change compose: "after the shock, does this price move help?". The verdict looks
at the item's own contribution profit, which is the quantity eps* is defined on;
substitution effects appear in the band profit outputs and the net break-even drop.
"""
from __future__ import annotations

import math
from typing import Mapping

from sim import matrix, model

DEFAULT_BANDS = {"low": -0.5, "medium": -1.0, "high": -1.8}
BAND_ORDER = ("low", "medium", "high")


def _expand_price_changes(baseline: Mapping, scenario: Mapping, new_costs: Mapping[str, float], old_costs: Mapping[str, float]) -> dict[str, float]:
    changes: dict[str, float] = {}
    by_cat = scenario.get("category_price_change") or {}
    explicit = scenario.get("price_change") or {}
    share = scenario.get("pass_through")
    for it in baseline["items"]:
        i = it["item_id"]
        if i in explicit:
            changes[i] = explicit[i]
        elif it["category"] in by_cat:
            changes[i] = by_cat[it["category"]]
        elif share and new_costs[i] != old_costs[i]:
            changes[i] = model.pass_through_price_change(old_costs[i], new_costs[i], it["price"], share)
    return {i: c for i, c in changes.items() if c != 0}


def _effective_elasticity(items: list[dict], band_eps: float, override: Mapping[str, float]) -> dict[str, float]:
    out = {}
    for it in items:
        out[it["item_id"]] = override.get(it["item_id"], override.get(it["category"], band_eps))
    return out


def _matrix_items(result_items: Mapping[str, dict], items: list[dict], weeks: int, baseline_side: bool) -> list[dict]:
    rows = []
    for it in items:
        r = result_items[it["item_id"]]
        r = r["baseline"] if baseline_side else r
        rows.append({"item_id": it["item_id"], "category": it["category"], "units": r["units"] * weeks, "cm": r["cm"]})
    return rows


def verdict(rise: bool, eps_star: float | None, pays: Mapping[str, bool]) -> str:
    """Plain-language verdict from which bands the change pays off under."""
    flags = list(pays.values())
    if all(flags):
        return "pays off under all bands"
    if not any(flags):
        return "loses money under all bands"
    direction = "less" if rise else "more"
    return f"pays off only if demand is {direction} elastic than {eps_star:.2f}"


def _price_test(it: dict, p1: float, cost: float, eff: Mapping[str, float], substitution: float,
                items: list[dict], new_costs: Mapping[str, float]) -> dict:
    p0 = it["price"]
    units = it["units"]
    rise = p1 > p0
    eps_star = model.break_even_elasticity(p0, p1, cost)
    ok_margin = p1 > cost and p0 > cost
    be_drop = model.break_even_drop(p0, p1, cost) if ok_margin else None
    cm_dest = model.destination_cm(
        [{**x, "price": x["price"]} for x in items], new_costs, it["item_id"]
    )
    be_net = (
        model.break_even_drop_net(p0, p1, cost, substitution, cm_dest)
        if ok_margin and cm_dest is not None and (p0 - cost) + (p1 - p0) - substitution * cm_dest > 0
        else None
    )
    ratio = p1 / p0
    by_band, pays = {}, {}
    for band, e in eff.items():
        own_units = model.demand(units, ratio, e)
        change = (p1 - cost) * own_units - (p0 - cost) * units
        predicted_drop = 1 - ratio**e
        by_band[band] = {"elasticity": e, "predicted_drop": predicted_drop, "own_profit_change": change}
        pays[band] = change > 0
    return {
        "p0": p0, "p1": p1, "unit_cost": cost,
        "break_even_elasticity": eps_star,
        "break_even_drop": be_drop,
        "break_even_drop_net": be_net,
        "by_band": by_band,
        "verdict": verdict(rise, eps_star, pays),
    }


def run_scenario(baseline: Mapping, scenario: Mapping | None = None) -> dict:
    scenario = scenario or {}
    items = baseline["items"]
    bands = scenario.get("bands") or DEFAULT_BANDS
    s = scenario.get("substitution", 0.25)
    override = scenario.get("elasticity_override") or {}
    weeks = baseline.get("window_weeks", 12)
    min_units = baseline.get("min_units", 50)
    factor = baseline.get("popularity_factor", 0.7)
    scope = scenario.get("scope", "category")

    old_costs = model.unit_costs(baseline["recipes"], baseline["ingredient_costs"])
    new_costs = model.unit_costs(baseline["recipes"], baseline["ingredient_costs"], scenario.get("cost_shock"))
    changes = _expand_price_changes(baseline, scenario, new_costs, old_costs)

    by_band = {}
    for band, eps in bands.items():
        by_band[band] = model.simulate(
            items, baseline["recipes"], baseline["ingredient_costs"],
            price_change=changes, cost_shock=scenario.get("cost_shock"),
            elasticity=_effective_elasticity(items, eps, override), substitution=s,
        )

    first = next(iter(by_band.values()))
    base_matrix = matrix.classify(_matrix_items(first["items"], items, weeks, True), scope, factor, min_units)
    scen_matrix = {
        b: matrix.classify(_matrix_items(r["items"], items, weeks, False), scope, factor, min_units)
        for b, r in by_band.items()
    }
    head = "medium" if "medium" in scen_matrix else next(iter(scen_matrix))
    classes = matrix.class_across_bands(scen_matrix, head)
    moves = matrix.class_moves(base_matrix, scen_matrix[head])

    out_items = {}
    for it in items:
        i = it["item_id"]
        row = {
            "name": it.get("name"), "category": it["category"],
            "baseline": first["items"][i]["baseline"],
            "by_band": {
                b: {k: r["items"][i][k] for k in ("units", "revenue", "ingredient_cost", "profit", "cm",
                                                  "food_cost_pct", "profit_change", "profit_change_pct")}
                for b, r in by_band.items()
            },
            "matrix": {**classes[i], **moves[i]},
            "price_test": None,
        }
        if i in changes:
            eff = {b: _effective_elasticity([it], e, override)[i] for b, e in bands.items()}
            row["price_test"] = _price_test(it, it["price"] * (1 + changes[i]), new_costs[i], eff, s, items, new_costs)
            row["price_test"]["price_change"] = changes[i]
        out_items[i] = row

    totals = {b: r["total"] for b, r in by_band.items()}
    weekly = [t["profit_change"] for t in totals.values()]
    return {
        "bands": dict(bands),
        "substitution": s,
        "price_changes": changes,
        "items": out_items,
        "total": {
            "baseline": first["total"]["baseline"],
            "by_band": totals,
            "profit_change_range": {"low": min(weekly), "high": max(weekly)},
            "annual_profit_change_range": {"low": model.annualize(min(weekly)), "high": model.annualize(max(weekly))},
        },
        "matrix": {
            "baseline_thresholds": base_matrix["thresholds"],
            "scenario_thresholds": scen_matrix[head]["thresholds"],
            "scope": scope,
        },
    }
