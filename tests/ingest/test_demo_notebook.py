import csv
import json
from pathlib import Path

from etl.baseline import baseline_from_warehouse
from etl.load import load_all
from etl.warehouse import get_connection
from sim.scenarios import run_scenario

ROOT = Path(__file__).resolve().parents[2]
NB = ROOT / "notebooks" / "invoice_parser_demo.ipynb"
DEMO = ROOT / "data" / "demo_approved"


def cells():
    return [c for c in json.loads(NB.read_text())["cells"] if c["cell_type"] == "code"]


def test_the_demo_notebook_is_executed_and_error_free():
    cs = cells()
    assert cs and all(c["execution_count"] for c in cs)
    assert not [o for c in cs for o in c["outputs"] if o["output_type"] == "error"]
    assert any("image/png" in o.get("data", {}) for c in cs for o in c["outputs"])


def test_the_demo_notebook_needs_no_key_and_defines_no_formulas():
    src = "\n".join("".join(c["source"]) for c in cells())
    assert "anthropic" not in src.lower() and "ANTHROPIC_API_KEY" not in src
    assert "def " not in src
    assert "LiveClient" not in src


def test_the_demo_notebook_writes_only_the_demo_overlay():
    src = "\n".join("".join(c["source"]) for c in cells())
    assert 'DEMO_DIR = ROOT / "data" / "demo_approved"' in src
    assert '"data" / "approved"' not in src and '"data" / "synthetic" /' not in src.replace('SYNTH = ROOT / "data" / "synthetic"', "")


def test_the_demo_overlay_is_small_and_matches_its_log():
    costs = list(csv.DictReader(open(DEMO / "ingredient_costs.csv")))
    log = list(csv.DictReader(open(DEMO / "approvals.csv")))
    assert {r["ingredient_id"] for r in costs} == {"ribeye", "sirloin", "short_rib", "ground_beef", "mozzarella"}
    assert sorted(r["decision"] for r in log) == ["approve"] * 5 + ["reject"] * 2
    edited = [r for r in log if "edited" in r["flags"]]
    assert len(edited) == 1 and edited[0]["corrected_value"] == "ingredient_id=mozzarella"
    assert all(r["approved_at"] == "2025-12-16T12:00:00Z" for r in log)       # a fixed time: the committed files are stable


def test_the_demo_overlay_moves_a_menu_class_only_when_asked_for():
    plain, merged = get_connection(":memory:"), get_connection(":memory:")
    load_all(plain)
    load_all(merged, with_approved=True, approved_dir=DEMO)
    a, b = run_scenario(baseline_from_warehouse(plain), {}), run_scenario(baseline_from_warehouse(merged), {})
    moved = {i: (a["items"][i]["matrix"]["baseline_class"], b["items"][i]["matrix"]["baseline_class"])
             for i in a["items"] if a["items"][i]["matrix"]["baseline_class"] != b["items"][i]["matrix"]["baseline_class"]}
    assert moved == {"short_rib": ("Puzzle", "Dog"), "philly": ("Dog", "Puzzle"), "veggie_burger": ("Dog", "Puzzle")}   # the burgers moved with their category thresholds
    assert b["total"]["baseline"]["profit"] < a["total"]["baseline"]["profit"]
