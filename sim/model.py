"""Reference simulation model: pure functions, plain data in and out.

No DuckDB, no pandas, no ground truth. The JS port in dashboard/sim.js must
match these functions (golden fixtures, parity test).

Data shapes
    items          list of {"item_id", "category", "price", "units"}   (units = baseline weekly units)
    recipes        {item_id: {ingredient_id: qty_per_serving}}
    ingredient_costs {ingredient_id: unit_cost}
    price_change   {item_id: fractional change, e.g. 0.05 for +5%}
    cost_shock     {ingredient_id: fractional change, e.g. 0.20 for +20%}
    elasticity     one number for every item, or {item_id: number} (missing ids use `default_elasticity`)

Demand is constant elasticity: units = baseline x (P1 / P0) ** elasticity, meant for
price changes within about +/-15%. Substitution is single pass: a share s of the
buyers an item loses (or gains, on a price cut) moves to (or comes from) the other
items in its category in proportion to their baseline units.
"""
from __future__ import annotations

import math
from typing import Mapping

WEEKS_PER_YEAR = 52


def unit_costs(
    recipes: Mapping[str, Mapping[str, float]],
    ingredient_costs: Mapping[str, float],
    cost_shock: Mapping[str, float] | None = None,
) -> dict[str, float]:
    """Plate cost per item: sum of recipe quantity x (shocked) ingredient cost."""
    shock = cost_shock or {}
    return {
        item: sum(qty * ingredient_costs[ing] * (1 + shock.get(ing, 0.0)) for ing, qty in recipe.items())
        for item, recipe in recipes.items()
    }


def _eps(elasticity, item_id: str) -> float:
    if isinstance(elasticity, Mapping):
        return elasticity[item_id]
    return elasticity


def demand(units: float, price_ratio: float, elasticity: float) -> float:
    """Constant-elasticity demand."""
    return units * price_ratio**elasticity


def simulate(
    items: list[dict],
    recipes: Mapping[str, Mapping[str, float]],
    ingredient_costs: Mapping[str, float],
    price_change: Mapping[str, float] | None = None,
    cost_shock: Mapping[str, float] | None = None,
    elasticity: float | Mapping[str, float] = -1.0,
    substitution: float = 0.25,
) -> dict:
    """Run one scenario. Returns per-item rows, menu totals and the baseline for comparison.

    Baseline = current prices and costs at baseline units. Units are clamped at 0
    (an extreme price cut cannot cannibalize more buyers than a neighbour has).
    """
    price_change = price_change or {}
    base_cost = unit_costs(recipes, ingredient_costs)
    new_cost = unit_costs(recipes, ingredient_costs, cost_shock)

    ids = [i["item_id"] for i in items]
    own = {}
    for it in items:
        ratio = 1 + price_change.get(it["item_id"], 0.0)
        own[it["item_id"]] = demand(it["units"], ratio, _eps(elasticity, it["item_id"]))

    inflow = {i: 0.0 for i in ids}
    for j in items:
        lost = j["units"] - own[j["item_id"]]  # negative on a price cut: items pull buyers in
        if lost == 0:
            continue
        others = [k for k in items if k["category"] == j["category"] and k["item_id"] != j["item_id"]]
        pop = sum(k["units"] for k in others)
        if pop == 0:
            continue
        for k in others:
            inflow[k["item_id"]] += substitution * lost * k["units"] / pop

    rows = {}
    for it in items:
        i = it["item_id"]
        price0, price1 = it["price"], it["price"] * (1 + price_change.get(i, 0.0))
        units0, units1 = it["units"], max(0.0, own[i] + inflow[i])
        row = _row(price1, new_cost[i], units1)
        base = _row(price0, base_cost[i], units0)
        row["baseline"] = base
        row["profit_change"] = row["profit"] - base["profit"]
        row["profit_change_pct"] = row["profit_change"] / base["profit"] if base["profit"] else None
        rows[i] = row

    total = _total([r for r in rows.values()])
    base_total = _total([r["baseline"] for r in rows.values()])
    total["baseline"] = base_total
    total["profit_change"] = total["profit"] - base_total["profit"]
    total["profit_change_pct"] = total["profit_change"] / base_total["profit"] if base_total["profit"] else None
    total["annual_profit_change"] = total["profit_change"] * WEEKS_PER_YEAR
    return {"items": rows, "total": total}


def _row(price: float, cost: float, units: float) -> dict:
    return {
        "price": price,
        "unit_cost": cost,
        "units": units,
        "revenue": price * units,
        "ingredient_cost": cost * units,
        "cm": price - cost,
        "food_cost_pct": cost / price if price else None,
        "profit": (price - cost) * units,
    }


def _total(rows: list[dict]) -> dict:
    return {k: sum(r[k] for r in rows) for k in ("units", "revenue", "ingredient_cost", "profit")}


def break_even_elasticity(p0: float, p1: float, cost: float) -> float | None:
    """Elasticity at which a price change leaves item contribution profit unchanged
    (no substitution): ln((P0 - c) / (P1 - c)) / ln(P1 / P0).

    Undefined (None) when the price does not change or either margin is not positive.
    A rise pays off if demand is less elastic than this; a cut pays off if more elastic.
    """
    if p0 == p1 or p0 <= cost or p1 <= cost:
        return None
    return math.log((p0 - cost) / (p1 - cost)) / math.log(p1 / p0)


def break_even_drop(p0: float, p1: float, cost: float) -> float:
    """Largest volume drop a price change can absorb with no substitution: dP / (CM + dP).

    Negative on a price cut: the volume gain needed.
    """
    dp = p1 - p0
    return dp / ((p0 - cost) + dp)


def break_even_drop_net(p0: float, p1: float, cost: float, substitution: float, cm_dest: float) -> float:
    """As break_even_drop, but a share `substitution` of lost buyers buy a same-category
    item earning `cm_dest` per unit: dP / (CM + dP - s x CM_dest)."""
    dp = p1 - p0
    return dp / ((p0 - cost) + dp - substitution * cm_dest)


def destination_cm(items: list[dict], costs: Mapping[str, float], item_id: str) -> float | None:
    """Popularity-weighted contribution margin of the other items in the same category."""
    me = next(i for i in items if i["item_id"] == item_id)
    others = [k for k in items if k["category"] == me["category"] and k["item_id"] != item_id]
    pop = sum(k["units"] for k in others)
    if pop == 0:
        return None
    return sum(k["units"] * (k["price"] - costs[k["item_id"]]) for k in others) / pop


def pass_through_price_change(unit_cost_before: float, unit_cost_after: float, price: float, share: float) -> float:
    """Fractional price rise that recovers `share` of a unit-cost increase."""
    return share * (unit_cost_after - unit_cost_before) / price


def annualize(weekly: float) -> float:
    return weekly * WEEKS_PER_YEAR
