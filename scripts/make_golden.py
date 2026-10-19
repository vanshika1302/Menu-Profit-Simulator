"""Write golden scenarios (inputs plus Python reference outputs) for the JS parity test.

    python scripts/make_golden.py

Output: tests/fixtures/golden.json. The Python model in sim/ is the reference; the JS port
in dashboard/sim.js must reproduce every number to 1e-9 relative and every string, class
and rank exactly (tests/parity.mjs).
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from etl.baseline import baseline_from_warehouse  # noqa: E402
from etl.load import load_all  # noqa: E402
from etl.warehouse import get_connection  # noqa: E402
from sim import model  # noqa: E402
from sim.experiments import GUARDRAILS, STOP_RULES, build_backlog  # noqa: E402
from sim.scenarios import run_scenario  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "golden.json"
BEEF = {k: 0.20 for k in ("ribeye", "sirloin", "short_rib", "ground_beef", "shaved_beef")}


def baselines() -> dict:
    con = get_connection(":memory:")
    load_all(con)
    base = baseline_from_warehouse(con)
    con.close()
    low = copy.deepcopy(base)  # one item below the 50-unit minimum over the window
    for it in low["items"]:
        if it["item_id"] == "veggie_burger":
            it["units"] = 2.0
    low["weekly_units_history"]["veggie_burger"] = [2.0, 1.0, 3.0, 2.0, 2.0, 1.0, 3.0, 2.0, 2.0, 2.0, 1.0, 3.0]
    return {"default": base, "insufficient": low}


def eps_at_break_even(base: dict, item: str, pct: float) -> float:
    it = next(i for i in base["items"] if i["item_id"] == item)
    cost = model.unit_costs(base["recipes"], base["ingredient_costs"])[item]
    return model.break_even_elasticity(it["price"], it["price"] * (1 + pct), cost)


def scenarios(base: dict) -> list[dict]:
    S = []

    def add(name, scenario=None, params=None, baseline="default"):
        S.append({"name": name, "scenario": scenario or {}, "params": params or {}, "baseline": baseline})

    add("no change")
    add("price rise 5% single item", {"price_change": {"ribeye": 0.05}})
    add("price rise 10% single item", {"price_change": {"classic_burger": 0.10}})
    add("price cut 8% single item", {"price_change": {"wings": -0.08}})
    add("price rise 15% edge of range", {"price_change": {"salmon": 0.15}})
    add("category wide 5%", {"category_price_change": {"Entrees": 0.05}})
    add("category wide cut 5%", {"category_price_change": {"Desserts": -0.05}})
    add("category with item exception", {"category_price_change": {"Burgers and sandwiches": 0.05}, "price_change": {"veggie_burger": 0.0}})
    add("two categories", {"category_price_change": {"Entrees": 0.05, "Pasta and bowls": 0.10}})
    add("beef shock 20%", {"cost_shock": BEEF})
    add("beef shock 50%", {"cost_shock": {k: 0.5 for k in BEEF}})
    add("beef shock -10%", {"cost_shock": {k: -0.10 for k in BEEF}})
    add("cost shock cheese", {"cost_shock": {"cheddar": 0.3, "mozzarella": 0.3}})
    add("combined beef shock and burger price", {"cost_shock": BEEF, "price_change": {"classic_burger": 0.05, "bacon_burger": 0.05}})
    add("combined shock and category price", {"cost_shock": BEEF, "category_price_change": {"Entrees": 0.05}})
    add("pass-through 50%", {"cost_shock": BEEF, "pass_through": 0.5})
    add("pass-through 100%", {"cost_shock": BEEF, "pass_through": 1.0})
    for s in (0.0, 0.25, 1.0):
        add(f"substitution {int(s * 100)}%", {"price_change": {"classic_burger": 0.10, "wings": -0.10}, "substitution": s})
    add("custom bands", {"price_change": {"ribeye": 0.05}, "bands": {"low": -0.3, "medium": -0.8, "high": -2.5}})
    add("two bands only", {"price_change": {"ribeye": 0.05}, "bands": {"low": -0.5, "high": -1.8}})
    add("item override", {"price_change": {"ribeye": 0.05}, "elasticity_override": {"ribeye": -1.3}})
    add("category override", {"category_price_change": {"Entrees": 0.05}, "elasticity_override": {"Entrees": -0.6}})
    add("override beats category", {"category_price_change": {"Entrees": 0.05}, "elasticity_override": {"Entrees": -0.6, "ribeye": -1.7}})
    add("whole menu scope", {"cost_shock": BEEF, "price_change": {"ribeye": 0.05}, "scope": "menu"})
    add("verdict loses everywhere", {"price_change": {"ribeye": 0.05}, "bands": {"low": -4.0, "medium": -5.0, "high": -6.0}})
    add("verdict pays everywhere", {"price_change": {"ribeye": 0.05}, "bands": {"low": -0.3, "medium": -0.6, "high": -1.2}})
    be = eps_at_break_even(base, "ribeye", 0.05)
    add("change at the break-even", {"price_change": {"ribeye": 0.05}, "elasticity_override": {"ribeye": be}})
    add("insufficient-data item", {"cost_shock": BEEF, "price_change": {"classic_burger": 0.05}}, baseline="insufficient")
    add("insufficient-data whole menu", {"price_change": {"veggie_burger": 0.05}, "scope": "menu"}, baseline="insufficient")
    add("pooled category test", {"price_change": {"ribeye": 0.05, "sirloin": 0.05, "short_rib": 0.05}})
    add("backlog high cap", {"price_change": {"ribeye": 0.05}}, {"cap_weeks": 10**6})
    add("backlog carryover 0 and 3 weeks cap", {"price_change": {"classic_burger": 0.15}}, {"cap_weeks": 100, "carryover_m": 0})
    add("backlog default step 10%", {}, {"default_price_step": 0.10, "cap_weeks": 2000})
    return S


def strip_constants(entry: dict) -> dict:
    return {k: v for k, v in entry.items() if k not in ("guardrails", "stop_rules")}


def main() -> None:
    bases = baselines()
    cases = []
    for sc in scenarios(bases["default"]):
        base = bases[sc["baseline"]]
        result = run_scenario(base, sc["scenario"])
        backlog = build_backlog(base, result, sc["params"])
        cases.append({
            **sc,
            "expected": {
                "result": result,
                "backlog": {k: [strip_constants(e) for e in v] for k, v in backlog.items() if k != "all"},
            },
        })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {"baselines": bases, "constants": {"guardrails": GUARDRAILS, "stop_rules": STOP_RULES}, "cases": cases}
    OUT.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
    print(f"{len(cases)} cases, {OUT.stat().st_size / 1e6:.2f} MB -> {OUT}")


if __name__ == "__main__":
    main()
