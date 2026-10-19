"""Render dashboard/template.html into the self-contained root index.html.

    python scripts/export_dashboard.py

Inlines dashboard/sim.js and the exported data (baseline from the warehouse plus validation
AGGREGATES). Per-item ground truth is never inlined: the validation JSON's per-item `detail`
and the recovery per-entry rows are dropped here, and tests/test_dashboard.py scans the output.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from etl.baseline import baseline_from_warehouse  # noqa: E402
from etl.load import DATA_DIR, load_all  # noqa: E402
from etl.warehouse import get_connection  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "dashboard" / "template.html"
SIM_JS = ROOT / "dashboard" / "sim.js"
OUT = ROOT / "index.html"

# Presentation groups for the cost-shock lever.
GROUP_LABELS = {
    "beef": "Beef (all cuts)", "poultry": "Chicken", "seafood": "Seafood", "pork": "Bacon",
    "dairy": "Dairy and eggs", "produce": "Produce and grains", "dry": "Dry goods, buns and oil",
    "drinks": "Drinks", "all": "Every ingredient",
}
GROUPS = {
    "beef": ["ribeye", "sirloin", "short_rib", "ground_beef", "shaved_beef"],
    "poultry": ["chicken_breast", "chicken_wings"],
    "seafood": ["salmon", "cod", "shrimp", "calamari"],
    "pork": ["bacon"],
    "dairy": ["cheddar", "mozzarella", "parmesan", "provolone", "cream", "butter", "eggs", "cream_cheese", "ice_cream"],
    "produce": ["potato", "romaine", "mixed_greens", "tomato", "onion", "garlic", "lemon", "lime", "quinoa"],
    "dry": ["pasta", "flour", "sugar", "bun", "tortilla_chips", "graham", "chocolate", "oil", "soup_base",
            "tomato_sauce", "hot_sauce", "veggie_patty"],
    "drinks": ["soda_syrup", "draft_beer", "house_wine"],
}


def validation_aggregates() -> dict:
    res = json.loads((ROOT / "validation_results.json").read_text())
    rec = json.loads((ROOT / "validation_recovery.json").read_text())
    sc = res["scenario_scorecard"]
    nh = res["naive_history"]
    widths = {lab: [e["runs"][lab]["estimate_interval_width"] for e in rec["entries"]] for lab in ("at_cap", "planned_duration")}
    return {
        "band_hit": res["band_hit_rate"],
        "scenarios": sc["scenarios"],
        "coverage": sc["profit_range_coverage"],
        "verdicts": sc["verdicts"],
        "naive": {k: nh[k] for k in ("events", "median_abs_error", "mean_abs_error", "wrong_sign_share", "outside_band_share")},
        "recovery": {
            "reps": rec["reps"],
            "mean_decision_accuracy": rec["mean_decision_accuracy"],
            "mean_interval_width_at_cap": sum(widths["at_cap"]) / len(widths["at_cap"]),
            "mean_interval_width_planned": sum(widths["planned_duration"]) / len(widths["planned_duration"]),
        },
    }


def build_data() -> dict:
    con = get_connection(":memory:")
    load_all(con, DATA_DIR)
    baseline = baseline_from_warehouse(con)
    con.close()
    groups = dict(GROUPS)
    groups["all"] = sorted(baseline["ingredient_costs"])
    missing = {i for g in GROUPS.values() for i in g} ^ set(baseline["ingredient_costs"])
    assert not missing, f"ingredient groups out of sync with data: {missing}"
    return {
        "baseline": baseline,
        "validation": validation_aggregates(),
        "ingredient_groups": groups,
        "group_labels": GROUP_LABELS,
    }


def render() -> str:
    html = TEMPLATE.read_text()
    data = json.dumps(build_data(), separators=(",", ":")).replace("</", "<\\/")
    sim = SIM_JS.read_text().replace("</script", "<\\/script")
    assert "/*__SIM_JS__*/" in html and "/*__DATA__*/" in html
    return html.replace("/*__SIM_JS__*/", sim).replace("/*__DATA__*/", data)


if __name__ == "__main__":
    OUT.write_text(render())
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e3:.0f} KB)")
