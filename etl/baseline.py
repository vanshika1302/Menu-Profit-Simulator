"""Read the baseline out of the warehouse as plain data for sim/."""
from __future__ import annotations

import duckdb


def baseline_from_warehouse(con: duckdb.DuckDBPyConnection) -> dict:
    """{"items": [...], "recipes": {...}, "ingredient_costs": {...}, "window_weeks", "min_units"}.

    Item units are the trailing-window weekly average; prices and costs are the latest.
    """
    items = [
        {"item_id": r[0], "name": r[1], "category": r[2], "price": r[3], "units": r[4]}
        for r in con.execute(
            "SELECT item_id, name, category, price, weekly_units FROM v_item_cm ORDER BY item_id"
        ).fetchall()
    ]
    recipes: dict[str, dict[str, float]] = {}
    for item, ing, qty in con.execute("SELECT item_id, ingredient_id, qty_per_serving FROM raw_recipes").fetchall():
        recipes.setdefault(item, {})[ing] = qty
    costs = dict(con.execute("SELECT ingredient_id, unit_cost FROM v_latest_ingredient_cost").fetchall())
    history: dict[str, list[float]] = {}
    for item, units in con.execute(
        "SELECT s.item_id, s.units_sold FROM raw_weekly_sales s JOIN v_window_weeks w ON w.week_start = s.week_start "
        "ORDER BY s.item_id, s.week_start"
    ).fetchall():
        history.setdefault(item, []).append(float(units))
    window_weeks, min_units, factor = con.execute(
        "SELECT window_weeks, min_units, popularity_factor FROM config"
    ).fetchone()
    return {
        "items": items,
        "recipes": recipes,
        "ingredient_costs": costs,
        "weekly_units_history": history,
        "window_weeks": window_weeks,
        "min_units": min_units,
        "popularity_factor": factor,
    }
