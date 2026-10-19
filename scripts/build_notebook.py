"""Build and execute notebooks/menu_profit_analysis.ipynb.

    python etl/run_pipeline.py
    python scripts/build_notebook.py

The notebook is a presentation layer: it imports sim/, queries DuckDB through
etl.warehouse.get_connection(), reads the saved validation files, and defines no formulas.
"""
from __future__ import annotations

import sys
from pathlib import Path

import nbformat
from nbconvert.preprocessors import ExecutePreprocessor

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "notebooks" / "menu_profit_analysis.ipynb"

md = nbformat.v4.new_markdown_cell
code = nbformat.v4.new_code_cell

CELLS = [
md("""# Menu Profit Simulator: analysis

A synthetic 30-item bistro. The question: **which menu items and operational changes improve profit without hurting demand, and how sure can we be?**

Everything here is computed by the functions in `sim/` (the same model the dashboard runs in JavaScript) on data queried from DuckDB. The notebook defines no formulas. The data is synthetic and the demand truth is authored, so the validation section shows where the method works and where it fails, not real-world accuracy.

**Elasticity is an assumption.** Wherever a number depends on it, it is shown as a range across a low (-0.5), medium (-1.0) and high (-1.8) band."""),
code("""import json, sys
from pathlib import Path
ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt
import pandas as pd
from etl.warehouse import get_connection
from etl.baseline import baseline_from_warehouse
from sim.scenarios import run_scenario
from sim.matrix import classify
from sim.experiments import build_backlog

pd.options.display.float_format = "{:,.2f}".format
pd.options.display.width = 140
plt.rcParams.update({"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False, "font.size": 10})
CLASS_STYLE = {"Star": ("#2a78d6", "o"), "Plowhorse": ("#eb6834", "s"), "Puzzle": ("#1baf7a", "D"), "Dog": ("#d9467e", "^")}

con = get_connection(read_only=True)
baseline = baseline_from_warehouse(con)
BEEF = ["ribeye", "sirloin", "short_rib", "ground_beef", "shaved_beef"]
print(len(baseline["items"]), "items, trailing", baseline["window_weeks"], "weeks")"""),

md("## 1. Baseline margins\n\nItem cost is the recipe quantity times the latest ingredient cost (SQL view `v_item_cm`). Contribution margin (CM) is price minus that cost, in dollars per unit."),
code("""items = con.execute("SELECT * FROM v_item_cm ORDER BY weekly_contribution_profit DESC").df()
items[["name", "category", "price", "unit_cost", "cm", "food_cost_pct", "weekly_units", "weekly_contribution_profit"]].head(10)"""),
code("""from etl.run_queries import parse_queries
queries = parse_queries((ROOT / "sql" / "analysis_queries.sql").read_text())
cat = con.execute(queries["category_summary"]).df()
ax = cat.set_index("category")["weekly_contribution_profit"].sort_values().plot.barh(color="#2a78d6", figsize=(7, 3))
ax.set_xlabel("Weekly contribution profit ($)"); ax.set_ylabel(""); ax.set_title("Where the contribution profit comes from"); plt.show()"""),

md("## 2. The menu engineering matrix\n\nEach item is compared with its own category: popular if its share of the category's units is at least 70% of an equal share, high margin if its CM is at or above the category's unit-weighted average. Four to seven items per category makes the thresholds noisy."),
code("""rows = items.rename(columns={"window_units": "units"})[["item_id", "name", "category", "units", "cm"]].to_dict("records")
base_matrix = classify(rows, "category")
items["class"] = items["item_id"].map({i: r["class"] for i, r in base_matrix["items"].items()})
print(items["class"].value_counts().to_string())
fig, axes = plt.subplots(2, 3, figsize=(11, 6), sharex=False)
for ax, (category, grp) in zip(axes.ravel(), items.groupby("category")):
    t = base_matrix["thresholds"][category]
    for _, r in grp.iterrows():
        color, mk = CLASS_STYLE[r["class"]]
        share = base_matrix["items"][r["item_id"]]["share"]
        ax.scatter(share / t["popularity_threshold"], r["cm"] / t["margin_threshold"], c=color, marker=mk, s=60)
        ax.annotate(r["name"], (share / t["popularity_threshold"], r["cm"] / t["margin_threshold"]), fontsize=7, xytext=(4, 4), textcoords="offset points")
    ax.axvline(1, color="#ccc"); ax.axhline(1, color="#ccc"); ax.set_title(category, fontsize=9)
fig.supxlabel("Popularity vs category threshold (1.0 = threshold)"); fig.supylabel("CM vs category average"); plt.tight_layout(); plt.show()"""),

md("## 3. A beef cost shock\n\nBeef +20% flows through the recipes of the seven items that use it. With no price change there is no demand response, so the result does not depend on elasticity and the three bands agree."),
code("""shock = run_scenario(baseline, {"cost_shock": {i: 0.20 for i in BEEF}})
hit = pd.DataFrame([
    {"item": v["name"], "category": v["category"], "baseline CM": v["baseline"]["cm"], "shocked CM": v["by_band"]["medium"]["cm"],
     "weekly profit change": v["by_band"]["medium"]["profit_change"], "class": f'{v["matrix"]["baseline_class"]} -> {v["matrix"]["scenario_class"]}'}
    for v in shock["items"].values() if v["by_band"]["medium"]["profit_change"] != 0
]).sort_values("weekly profit change")
print("Menu weekly profit change:", {b: round(t["profit_change"]) for b, t in shock["total"]["by_band"].items()})
hit"""),

md("## 4. Price scenarios with elasticity bands\n\nA price rise on one item, +5%. The **break-even elasticity** is the demand response at which the change leaves that item's profit unchanged; a rise pays off if demand is *less* elastic than that. The hatched band is the assumed elasticity range. When the break-even sits inside the band, the verdict depends on an assumption nobody has measured."),
code("""scen = run_scenario(baseline, {"price_change": {i: 0.05 for i in ["ribeye", "classic_burger", "salmon", "fries", "wings", "chicken_parm"]}})
tests = pd.DataFrame([
    {"item": v["name"], "break-even elasticity": v["price_test"]["break_even_elasticity"], "break-even drop": v["price_test"]["break_even_drop"],
     "predicted drop (medium)": v["price_test"]["by_band"]["medium"]["predicted_drop"], "verdict": v["price_test"]["verdict"],
     "weekly change low band": v["by_band"]["low"]["profit_change"], "medium": v["by_band"]["medium"]["profit_change"], "high band": v["by_band"]["high"]["profit_change"]}
    for v in scen["items"].values() if v["price_test"]
])
tests"""),
code("""fig, ax = plt.subplots(figsize=(8, 3))
lo, hi = min(scen["bands"].values()), max(scen["bands"].values())
ax.axvspan(lo, hi, facecolor="none", hatch="///", edgecolor="#6f6d67", label="assumed elasticity band")
for k, (_, r) in enumerate(tests.iterrows()):
    ax.plot([r["break-even elasticity"]], [k], "|", color="black", markersize=18, mew=2.5)
ax.set_yticks(range(len(tests))); ax.set_yticklabels(tests["item"]); ax.set_xlim(-2.6, 0)
ax.set_xlabel("Elasticity (black line = break-even for a +5% rise)"); ax.legend(loc="lower left"); plt.tight_layout(); plt.show()
t = scen["total"]["profit_change_range"]; print(f"Menu weekly profit change across the bands: {t['low']:+,.0f} to {t['high']:+,.0f}")"""),

md("## 5. The substitution slider\n\nSubstitution (the share of lost buyers who switch to a similar dish) is also an assumption: the research found no usable within-menu rate. It cushions a price rise on a dish that has close neighbours."),
code("""rows = []
for s in range(0, 101, 10):
    r = run_scenario(baseline, {"price_change": {"classic_burger": 0.10}, "substitution": s / 100})
    t = r["items"]["classic_burger"]["price_test"]
    rows.append({"substitution %": s, "menu change, low band": r["total"]["by_band"]["low"]["profit_change"],
                 "menu change, high band": r["total"]["by_band"]["high"]["profit_change"],
                 "break-even drop (no substitution)": t["break_even_drop"], "break-even drop (net)": t["break_even_drop_net"]})
sub = pd.DataFrame(rows)
fig, axes = plt.subplots(1, 2, figsize=(10, 3.2))
axes[0].fill_between(sub["substitution %"], sub["menu change, high band"], sub["menu change, low band"], facecolor="none", hatch="///", edgecolor="#6f6d67")
axes[0].set_title("Burger +10%: menu weekly profit change"); axes[0].set_xlabel("Substitution share (%)"); axes[0].set_ylabel("$ per week")
axes[1].plot(sub["substitution %"], sub["break-even drop (no substitution)"] * 100, label="headline")
axes[1].plot(sub["substitution %"], sub["break-even drop (net)"] * 100, label="net of substitution")
axes[1].set_title("Largest volume drop the +10% can absorb"); axes[1].set_xlabel("Substitution share (%)"); axes[1].set_ylabel("%"); axes[1].legend()
plt.tight_layout(); plt.show()"""),

md("## 6. The experiment backlog\n\nElasticity is assumed, so the plan is to measure it. Each candidate test is scored by stake, how uncertain the decision is, feasibility and risk. Duration comes from the noise in daily profit, assuming one-day blocks and one block of carryover. **At this restaurant's noise level, nothing fits in 12 weeks.** The table shows the shortest tests; the chart shows how a bigger price step shortens the test."),
code("""res = run_scenario(baseline, {"price_change": {"ribeye": 0.05, "classic_burger": 0.05}})
bl = build_backlog(baseline, res)
print(len(bl["feasible_now"]), "feasible now;", len(bl["needs_pooling"]), "need pooling or a larger effect")
pd.DataFrame([{"rank": e["rank"], "target": e["target_name"], "type": e["type"], "evidence": e["evidence"], "weeks": e["duration_weeks"],
               "score": e["score"], **e["factors"]} for e in bl["needs_pooling"][:10]])"""),
code("""steps = [0.05, 0.10, 0.15]
weeks = {}
for item in ["classic_burger", "ribeye", "chicken_parm"]:
    ws = []
    for step in steps:
        entries = build_backlog(baseline, run_scenario(baseline, {"price_change": {item: step}}))["all"]
        ws.append(next(e["duration_weeks"] for e in entries if e["target"] == item and e["type"] == "Price switchback test"))
    weeks[item] = ws
fig, ax = plt.subplots(figsize=(7, 3.2))
for item, ws in weeks.items():
    ax.plot([s * 100 for s in steps], ws, marker="o", label=item)
ax.axhline(12, color="black", linestyle="--"); ax.text(5, 14, "12-week cap", fontsize=8)
ax.set_yscale("log"); ax.set_xlabel("Price step (%)"); ax.set_ylabel("Weeks to resolve the band"); ax.legend(); plt.tight_layout(); plt.show()"""),
code("""e = bl["needs_pooling"][0]
print(e["target_name"], "|", e["type"], "|", e["evidence"])
print("Hypothesis:", e["hypothesis"]); print("Decision:  ", e["decision_rule"])
print("Guardrails:", [(g["name"], g["stop_if_down_pct"]) for g in e["guardrails"]["metrics"]], "(" + e["guardrails"]["label"] + ")")
for k, v in e["stop_rules"].items(): print(f"Stop rule ({k}):", v)"""),

md("## 7. Validation against the authored truth\n\nThe generator authored each item's true elasticity and substitution. `sim/validation.py` is the only code that reads them. These results come from `validation_results.json` and `validation_recovery.json`, committed snapshots. There are no pass/fail bounds on any finding."),
code("""val = json.load(open(ROOT / "validation_results.json")); rec = json.load(open(ROOT / "validation_recovery.json"))
bh, sc, nh = val["band_hit_rate"], val["scenario_scorecard"], val["naive_history"]
pd.DataFrame([
    ["True elasticity inside the band", f'{bh["rate"]:.0%}', f'{bh["inside_band"]} of {bh["items"]} items; misses are all in Drinks and sides'],
    ["Profit range covers the truth", f'{sc["profit_range_coverage"]["rate"]:.0%}', f'{sc["scenarios"]} scenarios (+5% and +10% on each item); misses are all on the optimistic side'],
    ["Medium-band headline has the right sign", f'{sc["verdicts"]["medium_band_sign_accuracy"]:.0%}', f'{sc["verdicts"]["medium_band_says_pays_when_truth_loses"]} cases say "pays off" when the truth loses'],
    ["Verdicts that are decisive", f'{sc["verdicts"]["pays_off_under_all_bands"] + sc["verdicts"]["loses_under_all_bands"]} of {sc["verdicts"]["total"]}', "the break-even usually sits inside a band this wide"],
    ["Naive before/after, median abs error", f'{nh["median_abs_error"]:.2f}', f'{nh["events"]} historical price changes; {nh["wrong_sign_share"]:.0%} have the wrong sign'],
    ["Switchback recovery at the 12-week cap", f'{rec["mean_decision_accuracy"]["at_cap"]:.0%}', f'{rec["reps"]} replications per entry; about a coin flip'],
    ["Switchback recovery at the powered duration", f'{rec["mean_decision_accuracy"]["planned_duration"]:.0%}', "durations of years, so not achievable in practice"],
], columns=["Check", "Result", "Note"])"""),
code("""ev = pd.DataFrame(nh["detail"])
fig, ax = plt.subplots(figsize=(6, 4.2))
ax.axhspan(-1.8, -0.5, facecolor="none", hatch="///", edgecolor="#6f6d67")
ax.plot([-3.6, 0.2], [-3.6, 0.2], color="#bbb", linestyle="--")
ax.scatter(ev["true"], ev["naive"], c="#eb6834", s=45, zorder=3)
for _, r in ev.iterrows(): ax.annotate(r["item"], (r["true"], r["naive"]), fontsize=7, xytext=(4, 3), textcoords="offset points")
ax.set_xlabel("True elasticity (authored)"); ax.set_ylabel("Naive before/after estimate"); ax.set_title("History alone gives a noisy, sometimes wrong-signed answer")
plt.tight_layout(); plt.show()"""),
md("""## Takeaways

* Margins and the matrix are descriptive and solid; they come straight from recipes, costs and sales.
* A cost shock alone is unambiguous. A price change is not: its sign usually depends on an elasticity nobody has measured, so the output is a range plus a break-even.
* Price history is confounded and gives a poor estimate (median error 0.64, two of nine with the wrong sign), which is why the project recommends experiments.
* At one restaurant's noise level, no single-item price test fits in a quarter. The honest options are larger effects, pooled items or longer tests.

Limitations are listed in the README: synthetic data and authored truth, assumed elasticity bands, single-pass substitution, no waste or yield, total units as a traffic proxy, assumed carryover and noise, policy-choice guardrails, weak evidence for menu-design and portion tests."""),
]


def main() -> None:
    nb = nbformat.v4.new_notebook(cells=CELLS)
    nb.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
    ExecutePreprocessor(timeout=600, kernel_name="python3").preprocess(nb, {"metadata": {"path": str(OUT.parent)}})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(nb, OUT)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
