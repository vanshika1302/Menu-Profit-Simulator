"""Build and execute notebooks/invoice_parser_demo.ipynb.

    python scripts/build_parser_notebook.py

Runs on committed recordings of the model when they exist for the demo invoice, and says so; otherwise it
falls back to the rule-based baseline and says that instead. It needs no API key either way. It also
regenerates the small demo overlay in data/demo_approved/ (never data/approved/ or data/synthetic/).
"""
from __future__ import annotations

from pathlib import Path

import nbformat
from nbconvert.preprocessors import ExecutePreprocessor

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "notebooks" / "invoice_parser_demo.ipynb"
md, code = nbformat.v4.new_markdown_cell, nbformat.v4.new_code_cell

CELLS = [
md("""# Invoice parser demo: from a supplier invoice to a changed menu decision

The Menu Profit Simulator's costs were typed in as CSVs. A restaurant has **invoices**. This notebook follows one constructed invoice through the parser extension:

1. an LLM **reads** the text and copies raw fields plus a quote of each line (it never converts a unit or does arithmetic);
2. plain **code** converts units, computes costs, checks the line totals and flags anything uncertain;
3. a **person** reviews the staged rows and approves them (here a reviewer's decisions are simulated by code, and said so);
4. the unchanged simulator is rebuilt on the approved rows, and menu engineering classes move.

The invoice, the supplier and the prices are constructed. The evaluation set is synthetic and rendered by the project's own generator, so the scores at the end show how the method behaves, not real-world accuracy."""),
code("""import csv, shutil, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(ROOT))

import json
import matplotlib.pyplot as plt
import pandas as pd
from etl.baseline import baseline_from_warehouse
from etl.load import load_all
from etl.warehouse import get_connection
from ingest import apply as ap
from ingest import model_client as mc
from ingest.baseline_extractor import rule_based_extractor
from ingest.parse import load_catalogue, parse_invoice
from ingest.stage import read_staging, write_meta, write_staging
from sim.scenarios import run_scenario

pd.options.display.width = 160
pd.options.display.max_colwidth = 70
plt.rcParams.update({"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False, "font.size": 10})
SYNTH = ROOT / "data" / "synthetic"
DEMO_DIR = ROOT / "data" / "demo_approved"      # the committed demo overlay, never data/approved/"""),

md("## 1. The invoice\n\nA constructed invoice: four beef lines (one catch-weight), a vague cheese line, a lettuce line priced per bunch, and a fuel surcharge."),
code("""text = (ROOT / "data" / "demo" / "invoice_beef_spike.txt").read_text()
print(text)"""),

md("## 2. Parse\n\nThe parser sends the text to the model behind one interface and gets back raw strings and a source quote for every line. Everything after that is code."),
code("""catalogue = load_catalogue(SYNTH)          # with the existing cost rows, so an invoice into an existing week is flagged as an update
summary = mc.recordings_summary(ROOT / "data" / "recordings") if (ROOT / "data" / "recordings").is_dir() else {"models": []}
label = summary["models"][0] if len(summary["models"]) == 1 else mc.DEFAULT_MODEL
recorded = mc.RecordedClient(ROOT / "data" / "recordings", model=label, prompt_version=mc.PROMPT_VERSIONS["invoice"])
try:
    result = parse_invoice(text, recorded, catalogue, "invoice_beef_spike.txt")
    producer = f"recorded responses from {label}"
    if label.startswith(mc.CLAUDE_CODE_PREFIX):
        producer += " (run through Claude Code's headless mode with all tools disabled, not the Anthropic API)"
except mc.MissingRecording:
    result = parse_invoice(text, mc.StubClient(rule_based_extractor), catalogue, "invoice_beef_spike.txt")
    producer = "the rule-based baseline (there is no recording of the model for this invoice yet)"
print("The invoice was read by:", producer)
staged = pd.DataFrame([{"kind": r.kind, "status": r.status, "ingredient": r.ingredient_id, "week": r.effective_week,
                        "unit cost": r.unit_cost, "flags": ", ".join(r.flags), "why": r.reason, "source line": r.source_line}
                       for r in sorted(result.rows, key=lambda r: ({"flagged": 0, "proposed": 1, "skipped": 2}[r.status], r.source_line or 0))])
staged"""),
md("Flagged rows come first. Each row carries the quoted source line, so a reviewer sees the evidence next to the number. The unit cost is **per pound** (or per quart, each, ...: the ingredient's own unit), computed by code: the `4/5 LB` case is 20 lb, so $560.00 is $28.00 per lb, and the catch-weight line is billed on the 41.2 lb actually received."),
code("""quotes = {r.source_line: r.source_quote for r in result.rows if r.source_quote}      # one quote per source line
pd.DataFrame([{"line": n, "quote": q} for n, q in sorted(quotes.items())])"""),

md("""## 3. Review

A person edits the `decision` column and, where needed, `corrected_value`. There is **no bulk approval**: every row needs an explicit decision. Here the reviewer's choices are simulated by code that follows the flags:

* approve the rows that came out clean;
* a **vague line** (`CHEESE SHREDDED`) is mozzarella: confirm it if the reader already guessed that, or correct it if the reader called it a new ingredient (and reject that proposed new ingredient);
* a **catch-weight line** whose received weight the reader could not find is costed by the reviewer from the invoice, which bills $20.10 per pound;
* reject the lettuce row (a price per bunch cannot become a per-head cost);
* leave the fuel surcharge alone (it was never costed)."""),
code("""tmp = Path(tempfile.mkdtemp())
staging_path = tmp / "invoice_beef_spike.csv"
write_staging(result.rows, staging_path)
write_meta(result.meta, staging_path)
recs = list(csv.DictReader(open(staging_path, newline="")))
for r in recs:
    flags = r["flags"].split(";") if r["flags"] else []
    if r["status"] == "skipped":
        continue                                                       # a fee: nothing to apply, leave it undecided
    if r["kind"] == "ingredient":
        r["decision"] = "reject"                                       # a proposed new ingredient: the cheese is not new
    elif "unconvertible_unit" in flags:
        r["decision"] = "reject"                                       # priced per bunch: no safe conversion
    elif "needs_cost" in flags and r["ingredient_id"] == "sirloin":
        r["decision"], r["corrected_value"] = "approve", "20.1"        # the invoice bills $20.10 per lb
    elif "new_ingredient" in flags:
        r["decision"], r["corrected_value"] = "approve", "ingredient_id=mozzarella"
    elif "ambiguous_name" in flags:
        r["decision"] = "approve"                                      # the reviewer confirms it is mozzarella
    elif r["status"] == "proposed":
        r["decision"] = "approve"
with open(staging_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(recs[0].keys()), lineterminator="\\n")
    w.writeheader(); w.writerows(recs)
pd.DataFrame([{k: r[k] for k in ("kind", "ingredient_id", "status", "flags", "decision", "corrected_value")} for r in recs])"""),
md("`apply` is a dry run unless told to write. It re-checks every row and corrections (the ingredient must exist, numbers must be positive) and shows what each approval would replace."),
code("""plan = ap.plan(staging_path, SYNTH, DEMO_DIR)
print(plan.describe())"""),
code("""if DEMO_DIR.exists():
    shutil.rmtree(DEMO_DIR)
ap.write(plan, DEMO_DIR, now=datetime(2025, 12, 16, 12, 0, tzinfo=timezone.utc))   # a fixed time keeps the committed demo files stable
for name in ("ingredient_costs.csv", "approvals.csv"):
    print(f"--- data/demo_approved/{name}"); print((DEMO_DIR / name).read_text())"""),

md("## 4. The simulator, rebuilt on the approved rows\n\nThe overlay is merged only when asked for (`with_approved=True`); the portfolio's committed results stay built on the synthetic base. The simulator itself is unchanged."),
code("""con_a, con_b = get_connection(":memory:"), get_connection(":memory:")
load_all(con_a)
load_all(con_b, with_approved=True, approved_dir=DEMO_DIR)
before, after = baseline_from_warehouse(con_a), baseline_from_warehouse(con_b)
r0, r1 = run_scenario(before, {}), run_scenario(after, {})
rows = []
for i, v0 in r0["items"].items():
    v1 = r1["items"][i]
    if abs(v1["baseline"]["unit_cost"] - v0["baseline"]["unit_cost"]) > 1e-9:
        rows.append({"item": v0["name"], "cost before": v0["baseline"]["unit_cost"], "cost after": v1["baseline"]["unit_cost"],
                     "CM before": v0["baseline"]["cm"], "CM after": v1["baseline"]["cm"],
                     "weekly profit before": v0["baseline"]["profit"], "weekly profit after": v1["baseline"]["profit"],
                     "class before": v0["matrix"]["baseline_class"], "class after": v1["matrix"]["baseline_class"]})
changed = pd.DataFrame(rows).sort_values("weekly profit before", ascending=False)
changed.round(2)"""),
code("""moved = [(i, v0["matrix"]["baseline_class"], r1["items"][i]["matrix"]["baseline_class"], v0["name"]) for i, v0 in r0["items"].items()
         if v0["matrix"]["baseline_class"] != r1["items"][i]["matrix"]["baseline_class"]]
own = set(changed["item"])
print(f"{len(changed)} items changed cost; {len(moved)} items changed menu engineering class:")
for i, was, now, name in moved:
    print(f"  {name}: {was} -> {now}" + ("" if name in own else "   (its own cost did not change: its category's thresholds moved)"))
print(f"Menu weekly contribution profit: ${r0['total']['baseline']['profit']:,.0f} -> ${r1['total']['baseline']['profit']:,.0f}")"""),

md("## 5. How well does the parser read? (synthetic evaluation set)\n\nSixty documents rendered from the synthetic restaurant, with the answers known, scored by `ingest/scorecard.py`. The rule-based baseline was **written knowing the generator's layouts**, so it is a favourable baseline: it reads the regular formats perfectly and fails on supplier name variants. The model's snapshot (scored once on the held-out test set, through Claude Code's headless mode) is shown beside it when it has been recorded."),
code("""snaps = {"rule-based baseline": json.load(open(ROOT / "ingest_eval_stub.json"))}
live = ROOT / "ingest_eval_live.json"
if live.exists():
    snaps[json.load(open(live))["model"]] = json.load(open(live))
else:
    print("No live-model snapshot has been recorded yet (ingest_eval_live.json): only the baseline is shown.")
tiers = []
for name, s in snaps.items():
    for tier, v in s["report"]["scorecard"]["by_tier"].items():
        tiers.append({"reader": name, "tier": tier, "F1": v["rows"]["f1"], "silent errors": v["buckets"]["silent_error"],
                      "fabricated": v["buckets"]["fabricated"], "omitted": v["buckets"]["omitted"]})
table = pd.DataFrame(tiers)
table.pivot(index="tier", columns="reader", values="F1").round(3)"""),
code("""fig, ax = plt.subplots(figsize=(8, 3.4))
pivot = table.pivot(index="tier", columns="reader", values="F1")
pivot.plot.barh(ax=ax, width=0.75)
ax.set_xlabel("Row F1 (1.0 = every row right)"); ax.set_ylabel(""); ax.set_xlim(0, 1.05); ax.legend(loc="lower left", fontsize=8)
plt.tight_layout(); plt.show()"""),
code("""head = []
for name, s in snaps.items():
    o = s["report"]["scorecard"]["overall"]; d = s["report"]["downstream"]
    head.append({"reader": name, "split": s["split"], "silent error rate": o["silent_error_rate"], "catch rate": o["catch_rate"],
                 "rows F1": o["rows"]["f1"], "class flips if all rows approved": d["approve_all"]["class_flips"],
                 "class flips if only unflagged approved": d["approve_unflagged"]["class_flips"],
                 "weekly profit error, approve all ($)": d["approve_all"]["weekly_profit_error"]})
pd.DataFrame(head).round(3)"""),
md("""## Takeaways

* The model **reads**; code **computes**. A unit conversion or a cost is never produced by the model, so the arithmetic is the same on every run and is tested with hand-computed cases.
* Every row is either right, or **flagged with a reason and a source quote**, or refused with no value. The number to watch is the **silent error rate** (a wrong, unflagged row): it is the only error a reviewer cannot see.
* A cost is not abstract: a new beef price moves an item's margin and can flip its menu class, and it also shifts its category's thresholds, so items whose own cost did not change can change class too. That is why the downstream effect of a parsing error is scored, with and without approving flagged rows.
* A person always approves. The overlay is opt-in and kept out of the portfolio's committed results.

**Limits.** The invoices are constructed or rendered by the project's own generator, so real invoices will be messier. There is no OCR, one call per document, no yield model, and beverage ingredients stocked in fluid ounces are refused. See the README for the full list."""),
]


def main() -> None:
    nb = nbformat.v4.new_notebook(cells=CELLS)
    nb.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
    ExecutePreprocessor(timeout=600, kernel_name="python3").preprocess(nb, {"metadata": {"path": str(OUT.parent)}})
    nbformat.write(nb, OUT)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
