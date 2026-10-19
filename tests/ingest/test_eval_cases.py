"""The evaluation set: counts, split, determinism, size, truth consistency, and recoverability."""
import collections
import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

from eval import generate_cases as gc
from ingest.normalise import parse_pack, unit_cost_from_case, unit_cost_from_unit_price
from ingest.stage import FLAGS

ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "data" / "eval"


def truths():
    return [json.loads(p.read_text()) for p in sorted((EVAL / "truth").glob("*.json"))]


def read(truth):
    return (EVAL / truth["source_file"]).read_text()


def test_counts_per_tier():
    m = json.loads((EVAL / "manifest.json").read_text())["cases"]
    c = collections.Counter((x["kind"], x["tier"]) for x in m)
    assert {t: c[("invoice", t)] for t in (1, 2, 3, 4)} == {1: 10, 2: 10, 3: 10, 4: 10}
    assert {t: c[("recipe", t)] for t in (1, 2, 3)} == {1: 5, 2: 5, 3: 4}
    assert c[("invoice", "handwritten")] + c[("recipe", "handwritten")] == 6
    assert len(m) == 60


def test_split_is_about_thirty_percent_and_spans_every_tier():
    m = json.loads((EVAL / "manifest.json").read_text())["cases"]
    test = [x for x in m if x["split"] == "test"]
    assert 0.2 <= len(test) / len(m) <= 0.35
    assert {x["split"] for x in m} == {"dev", "test"}
    for key in {(x["kind"], x["tier"]) for x in m if x["tier"] != "handwritten"}:
        assert any(x["split"] == "test" for x in m if (x["kind"], x["tier"]) == key), key


def test_regeneration_is_byte_identical(tmp_path):
    gc.generate(tmp_path / "eval")
    for f in sorted(EVAL.rglob("*")):
        if f.is_file():
            assert f.read_bytes() == (tmp_path / "eval" / f.relative_to(EVAL)).read_bytes(), f


def test_committed_files_are_under_a_megabyte():
    assert sum(f.stat().st_size for f in EVAL.rglob("*") if f.is_file()) < 1_000_000


def test_every_messiness_type_is_labelled_grounded_or_guessed():
    for t in truths():
        assert t["messiness"], t["case_id"]
        for m in t["messiness"]:
            assert m["basis"].split(" ")[0] in ("grounded", "guessed"), m


def test_supplier_names_are_invented():
    real = ("sysco", "us foods", "performance food", "gordon", "shamrock", "restaurant depot")
    for t in truths():
        text = read(t).lower()
        assert not any(r in text for r in real), t["case_id"]


def test_truth_is_well_formed_and_points_at_real_lines():
    ingredients = {r.split(",")[0] for r in (ROOT / "data/synthetic/ingredients.csv").read_text().splitlines()[1:]}
    items = {r.split(",")[0] for r in (ROOT / "data/synthetic/menu_items.csv").read_text().splitlines()[1:]}
    for t in truths():
        lines = read(t).splitlines()
        for row in t["rows"]:
            assert 1 <= row["source_line"] <= len(lines), t["case_id"]
            assert row["ingredient_id"] in ingredients | {"NEW"}
            assert set(row["flags"]) <= set(FLAGS)
            if t["kind"] == "recipe":
                assert row["item_id"] in items
        for s in t["skipped"]:
            assert 1 <= s["source_line"] <= len(lines)
        if t["kind"] == "invoice" and t["effective_week"] is not None:
            assert date.fromisoformat(t["effective_week"]).weekday() == 0, t["case_id"]  # always a Monday
            assert date.fromisoformat(t["invoice_date"]) - date.fromisoformat(t["effective_week"]) < timedelta(days=7)
            assert date.fromisoformat(t["invoice_date"]) >= date.fromisoformat(t["effective_week"])


def test_truth_never_appears_in_a_document():
    for t in truths():
        text = read(t)
        for banned in ("unit_cost", "ingredient_id", "effective_week", "qty_per_serving", "expected", "truth", "needs_cost",
                       "unconvertible_unit", "check_failed"):
            assert banned not in text, (t["case_id"], banned)


def test_tiers_one_and_two_are_recoverable_with_the_pure_unit_functions():
    """Rendering then parsing the rendered fields with ingest.normalise recovers the true unit cost,
    and each rendered field really is on the line the truth points to."""
    cat = gc.load_catalogue()
    checked = 0
    for t in truths():
        if t["kind"] != "invoice" or t["tier"] not in (1, 2):
            continue
        lines = read(t).splitlines()
        for row in t["rows"]:
            raw, unit = row["raw"], cat["ingredients"][row["ingredient_id"]]["unit"]
            line = lines[row["source_line"] - 1]
            assert raw["description"] in line and raw["unit_price"] in line and raw["extended_price"] in line
            price = float(raw["unit_price"].replace(",", ""))
            if raw["pack_text"]:
                assert raw["pack_text"] in line
                got = unit_cost_from_case(price, parse_pack(raw["pack_text"]), unit)
            else:
                from ingest.units import normalise_unit
                got = unit_cost_from_unit_price(price, normalise_unit(raw["price_unit"]), unit)
            assert got == pytest.approx(row["unit_cost"], rel=1e-9), (t["case_id"], row)
            checked += 1
    assert checked >= 150


def test_true_costs_are_close_to_the_synthetic_data():
    """The truth is derived from rendered cents, so it stays within rounding of the data's own costs."""
    cat = gc.load_catalogue()
    for t in truths():
        if t["kind"] != "invoice" or t["tier"] not in (1, 2) or not t.get("effective_week"):
            continue
        for row in t["rows"]:
            data_cost = cat["costs"][row["ingredient_id"]][t["effective_week"]]
            assert row["unit_cost"] == pytest.approx(data_cost, rel=0.06, abs=0.012), (t["case_id"], row)


def test_adversarial_cases_cover_every_trap_and_carry_their_flags():
    adv = [t for t in truths() if t["kind"] == "invoice" and t["tier"] == 4]
    assert {t["trap"] for t in adv} == set(gc.TRAPS)
    expect = {"missing_date": "missing_date", "unknown_pack_unit": "unconvertible_unit", "weight_to_volume": "unconvertible_unit",
              "ambiguous_name": "ambiguous_name", "new_ingredient": "new_ingredient", "unknown_can_size": "unconvertible_unit",
              "line_total_mismatch": "check_failed", "catch_weight_missing_received": "needs_cost", "duplicate_ingredient": "conflict"}
    for t in adv:
        flags = {f for r in t["rows"] for f in r["flags"]}
        if t["trap"] in expect:
            assert expect[t["trap"]] in flags, t["trap"]
        else:  # the injection case: every row is clean and nothing extra is expected
            assert flags == set() and len(t["rows"]) == 4
    injected = next(t for t in adv if t["trap"] == "injection")
    assert "ignore all previous instructions" in read(injected).lower()


def test_handwritten_cases_are_present_and_labelled_by_hand():
    hw = [t for t in truths() if t["tier"] == "handwritten"]
    assert len(hw) == 6 and {t["case_id"] for t in hw} == {f"hw_0{i}" for i in range(1, 7)}
    injection = next(t for t in hw if t["case_id"] == "hw_01")
    assert "saffron" in read(injection) and all(r["ingredient_id"] != "NEW" for r in injection["rows"])
    credit = next(t for t in hw if t["case_id"] == "hw_02")
    assert credit["rows"] == [] and len(credit["skipped"]) == 2
    nosrv = next(t for t in hw if t["case_id"] == "hw_03")
    assert all(r["qty_per_serving"] is None and r["flags"] == ["missing_servings"] for r in nosrv["rows"])


def test_the_generator_can_run_as_a_script(tmp_path):
    r = subprocess.run([sys.executable, "eval/generate_cases.py"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0 and "60" in r.stdout
