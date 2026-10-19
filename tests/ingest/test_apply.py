import csv
import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from etl.baseline import baseline_from_warehouse
from etl.load import load_all
from etl.warehouse import get_connection
from ingest import apply as ap
from ingest.stage import RunMeta, StagedRow, make_row_id, read_staging, write_meta, write_staging
from scripts import ingest_apply
from sim.scenarios import run_scenario

ROOT = Path(__file__).resolve().parents[2]
SYNTH = ROOT / "data" / "synthetic"
SHA = "ab" * 32
NOW = datetime(2025, 3, 10, 12, 0, tzinfo=timezone.utc)


def cost(line, ing="ribeye", week="2025-03-03", value=30.0, flags=(), **kw):
    return StagedRow.create(make_row_id(SHA, line, "cost"), "cost", flags=flags, ingredient_id=ing, effective_week=week,
                            unit_cost=value, source_line=line, source_quote=f"line {line}", **kw)


def recipe_line(line, ing, qty, dish="wings"):
    return StagedRow.create(make_row_id(SHA, line, "recipe_line"), "recipe_line", item_id=dish, ingredient_id=ing,
                            qty_per_serving=qty, source_line=line, source_quote=f"line {line}")


def new_ingredient(line, ing="truffle_oil", unit="gal"):
    return StagedRow.create(make_row_id(SHA, line, "ingredient"), "ingredient", flags=("new_ingredient",), ingredient_id=ing,
                            name="Truffle Oil", unit=unit, source_line=line, source_quote=f"line {line}")


def stage(tmp_path, rows, decisions=None, name="run.csv", sha=SHA):
    """Write a staging file and apply reviewer decisions {row_id: (decision, corrected)}."""
    p = tmp_path / name
    write_staging(rows, p)
    write_meta(RunMeta("invoice", "recorded", "m", "v", "v", "x.txt", sha), p)
    recs = list(csv.DictReader(open(p, newline="")))
    for r in recs:
        d = (decisions or {}).get(r["row_id"])
        if d:
            r["decision"], r["corrected_value"] = d[0], d[1] if len(d) > 1 else ""
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(recs[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(recs)
    return p


@pytest.fixture
def dirs(tmp_path):
    approved = tmp_path / "approved"
    return SYNTH, approved


def file_text(path):
    return Path(path).read_text() if Path(path).exists() else None


# ---------------------------------------------------------------- dry run, blank decisions, no bulk path
def test_a_dry_run_writes_nothing_and_blank_decisions_change_nothing(tmp_path, dirs):
    synth, approved = dirs
    a, b = cost(1), cost(2, ing="sirloin")
    p = stage(tmp_path, [a, b], {a.row_id: ("approve",)})
    plan = ap.plan(p, synth, approved)
    assert len(plan.approvals) == 1 and plan.untouched == 1
    assert "1 to approve" in plan.describe() and "1 undecided" in plan.describe()
    code = ingest_apply.main([str(p), "--data-dir", str(synth), "--approved-dir", str(approved)])
    assert code == 0 and not approved.exists()


def test_there_is_no_bulk_approval_option(capsys):
    with pytest.raises(SystemExit):
        ingest_apply.main(["--help"])
    out = capsys.readouterr().out
    assert "bulk" in out.lower() and "no bulk approval" in out.lower()   # the help says there is none
    assert "--approve-all" not in out and "--approve-unflagged" not in out
    with pytest.raises(SystemExit):
        ingest_apply.main(["x.csv", "--approve-all"])


def test_rejections_are_logged_but_change_no_data(tmp_path, dirs):
    synth, approved = dirs
    a = cost(1)
    p = stage(tmp_path, [a], {a.row_id: ("reject",)})
    ap.write(ap.plan(p, synth, approved), approved, NOW)
    assert not (approved / "ingredient_costs.csv").exists()
    log = list(csv.DictReader(open(approved / "approvals.csv")))
    assert [r["decision"] for r in log] == ["reject"]


# ---------------------------------------------------------------- writing the overlay
def test_approved_rows_are_written_in_the_overlay_shape(tmp_path, dirs):
    synth, approved = dirs
    rows = [cost(1, value=21.5), new_ingredient(2), recipe_line(3, "chicken_wings", 1.25)]
    p = stage(tmp_path, rows, {r.row_id: ("approve",) for r in rows})
    plan = ap.plan(p, synth, approved)
    assert not plan.errors
    ap.write(plan, approved, NOW)
    costs = list(csv.DictReader(open(approved / "ingredient_costs.csv")))
    assert costs == [{"ingredient_id": "ribeye", "effective_week": "2025-03-03", "unit_cost": "21.500000"}]
    assert list(csv.DictReader(open(approved / "ingredients.csv"))) == [{"ingredient_id": "truffle_oil", "name": "Truffle Oil", "unit": "gal"}]
    assert list(csv.DictReader(open(approved / "recipes.csv"))) == [{"item_id": "wings", "ingredient_id": "chicken_wings", "qty_per_serving": "1.250000"}]
    log = list(csv.DictReader(open(approved / "approvals.csv")))
    assert [r["decision"] for r in log] == ["approve"] * 3 and log[0]["approved_at"] == "2025-03-10T12:00:00Z"
    assert log[0]["source_sha256"] == SHA and log[0]["run_id"] == SHA[:12]
    assert not (synth.parent / "synthetic_edited").exists()


def test_synthetic_data_is_never_modified(tmp_path, dirs):
    synth, approved = dirs
    before = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in synth.glob("*.csv")}
    a = cost(1)
    ap.write(ap.plan(stage(tmp_path, [a], {a.row_id: ("approve",)}), synth, approved), approved, NOW)
    after = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in synth.glob("*.csv")}
    assert before == after


def test_a_later_run_beats_an_earlier_one_for_the_same_key(tmp_path, dirs):
    synth, approved = dirs
    first, second = cost(1, value=25.0), StagedRow.create(make_row_id("cd" * 32, 1, "cost"), "cost", ingredient_id="ribeye",
                                                          effective_week="2025-03-03", unit_cost=26.0, source_line=1)
    ap.write(ap.plan(stage(tmp_path, [first], {first.row_id: ("approve",)}, "a.csv"), synth, approved), approved, NOW)
    ap.write(ap.plan(stage(tmp_path, [second], {second.row_id: ("approve",)}, "b.csv", sha="cd" * 32), synth, approved), approved, NOW)
    rows = list(csv.DictReader(open(approved / "ingredient_costs.csv")))
    assert len(rows) == 1 and float(rows[0]["unit_cost"]) == 26.0
    assert len(list(csv.DictReader(open(approved / "approvals.csv")))) == 2


def test_an_approved_recipe_replaces_every_earlier_row_for_its_dish(tmp_path, dirs):
    synth, approved = dirs
    r1 = [recipe_line(1, "chicken_wings", 1.0), recipe_line(2, "hot_sauce", 0.1)]
    ap.write(ap.plan(stage(tmp_path, r1, {r.row_id: ("approve",) for r in r1}, "a.csv"), synth, approved), approved, NOW)
    r2 = StagedRow.create(make_row_id("cd" * 32, 1, "recipe_line"), "recipe_line", item_id="wings", ingredient_id="chicken_wings",
                          qty_per_serving=0.9, source_line=1)
    plan = ap.plan(stage(tmp_path, [r2], {r2.row_id: ("approve",)}, "b.csv", sha="cd" * 32), synth, approved)
    assert any("replaces all 3 existing recipe line(s)" in n for n in plan.recipe_notes)   # wings has three base lines
    ap.write(plan, approved, NOW)
    rows = list(csv.DictReader(open(approved / "recipes.csv")))
    assert [(r["ingredient_id"], float(r["qty_per_serving"])) for r in rows] == [("chicken_wings", 0.9)]


# ---------------------------------------------------------------- idempotence
def test_applying_the_same_decisions_twice_is_a_no_op(tmp_path, dirs):
    synth, approved = dirs
    a = cost(1, value=21.0)
    p = stage(tmp_path, [a], {a.row_id: ("approve",)})
    ap.write(ap.plan(p, synth, approved), approved, NOW)
    snapshot = {f.name: f.read_text() for f in approved.glob("*.csv")}
    again = ap.plan(p, synth, approved)
    assert again.already_applied == [a.row_id] and again.actions == [] and "1 already applied" in again.describe()
    ap.write(again, approved, NOW)
    assert {f.name: f.read_text() for f in approved.glob("*.csv")} == snapshot


# ---------------------------------------------------------------- corrections
def test_corrections_are_applied_and_logged_with_both_values(tmp_path, dirs):
    synth, approved = dirs
    a = cost(1, ing="ambiguous_guess", value=30.0, flags=("ambiguous_name",))
    fixed = ("approve", "ingredient_id=cheddar;unit_cost=3.10")
    p = stage(tmp_path, [a], {a.row_id: fixed})
    plan = ap.plan(p, synth, approved)
    assert not plan.errors and plan.approvals[0].edited
    ap.write(plan, approved, NOW)
    row = list(csv.DictReader(open(approved / "ingredient_costs.csv")))[0]
    assert row["ingredient_id"] == "cheddar" and float(row["unit_cost"]) == 3.10
    log = list(csv.DictReader(open(approved / "approvals.csv")))[0]
    assert log["original_value"] == "30.000000" and log["corrected_value"] == "ingredient_id=cheddar;unit_cost=3.10" and "edited" in log["flags"]


def test_a_bare_number_corrects_the_rows_value(tmp_path, dirs):
    synth, approved = dirs
    a = cost(1, value=30.0)
    plan = ap.plan(stage(tmp_path, [a], {a.row_id: ("approve", "22.5")}), synth, approved)
    assert plan.approvals[0].values["unit_cost"] == 22.5


@pytest.mark.parametrize("decision,why", [
    (("approve", "ingredient_id=not_an_ingredient"), "not in the catalogue"),
    (("approve", "-3"), "must be positive"),
    (("approve", "abc"), "not a number"),
    (("approve", "effective_week=2025-03-05"), "not a Monday"),
    (("approve", "effective_week=sometime"), "not a date"),
    (("approve", "colour=blue"), "cannot correct"),
])
def test_bad_corrections_are_rejected_and_nothing_is_written(tmp_path, dirs, decision, why):
    synth, approved = dirs
    a = cost(1)
    p = stage(tmp_path, [a], {a.row_id: decision})
    plan = ap.plan(p, synth, approved)
    assert plan.errors and why in plan.errors[0]
    assert ingest_apply.main([str(p), "--write", "--data-dir", str(synth), "--approved-dir", str(approved)]) == 1
    assert not approved.exists()
    with pytest.raises(ap.ApplyError):
        ap.write(plan, approved, NOW)


def test_a_row_with_no_value_cannot_be_approved_until_corrected(tmp_path, dirs):
    synth, approved = dirs
    a = cost(1, value=None, flags=("needs_cost",))
    assert "no cost" in ap.plan(stage(tmp_path, [a], {a.row_id: ("approve",)}), synth, approved).errors[0]
    ok = ap.plan(stage(tmp_path, [a], {a.row_id: ("approve", "21.0")}, "b.csv"), synth, approved)
    assert not ok.errors and ok.approvals[0].values["unit_cost"] == 21.0


def test_a_missing_week_can_be_supplied_by_correction(tmp_path, dirs):
    synth, approved = dirs
    a = cost(1, week="", flags=("missing_date",))
    assert "no effective week" in ap.plan(stage(tmp_path, [a], {a.row_id: ("approve",)}), synth, approved).errors[0]
    ok = ap.plan(stage(tmp_path, [a], {a.row_id: ("approve", "effective_week=2025-03-03")}, "b.csv"), synth, approved)
    assert not ok.errors


def test_skipped_lines_cannot_be_approved(tmp_path, dirs):
    synth, approved = dirs
    s = StagedRow.create("sk1", "cost", skipped=True, reason="fee", source_line=9)
    assert "nothing to apply" in ap.plan(stage(tmp_path, [s], {"sk1": ("approve",)}), synth, approved).errors[0]
    assert not ap.plan(stage(tmp_path, [s], {"sk1": ("reject",)}, "b.csv"), synth, approved).errors


def test_a_new_ingredient_approved_in_the_same_file_is_a_valid_target(tmp_path, dirs):
    synth, approved = dirs
    ing = new_ingredient(1)
    c = cost(2, ing="truffle_oil", value=6.0)
    p = stage(tmp_path, [ing, c], {ing.row_id: ("approve",), c.row_id: ("approve",)})
    assert not ap.plan(p, synth, approved).errors
    only_cost = stage(tmp_path, [ing, c], {c.row_id: ("approve",)}, "b.csv")
    assert "not in the catalogue" in ap.plan(only_cost, synth, approved).errors[0]


def test_a_bad_unit_on_a_new_ingredient_is_rejected(tmp_path, dirs):
    synth, approved = dirs
    ing = new_ingredient(1)
    assert "must be one of" in ap.plan(stage(tmp_path, [ing], {ing.row_id: ("approve", "unit=bunch")}), synth, approved).errors[0]


# ---------------------------------------------------------------- the loader: opt-in merge, default unchanged
def build(approved=None, with_approved=False):
    con = get_connection(":memory:")
    if approved is None:
        load_all(con)
    else:
        load_all(con, with_approved=with_approved, approved_dir=approved)
    return con


def test_the_default_load_is_byte_identical_to_before(tmp_path, dirs):
    synth, approved = dirs
    a = cost(1, value=30.0)
    ap.write(ap.plan(stage(tmp_path, [a], {a.row_id: ("approve",)}), synth, approved), approved, NOW)
    plain, ignoring = build(), build(approved, with_approved=False)       # an overlay exists but is not asked for
    for table in ("raw_ingredients", "raw_recipes", "raw_ingredient_costs", "raw_weekly_sales"):
        q = f"SELECT * FROM {table} ORDER BY ALL"
        assert plain.execute(q).fetchall() == ignoring.execute(q).fetchall(), table
    assert plain.execute("SELECT unit_cost FROM raw_ingredient_costs WHERE ingredient_id='ribeye' AND effective_week='2025-03-03'").fetchone()[0] != 30.0


def test_with_approved_merges_costs_recipes_and_ingredients(tmp_path, dirs):
    synth, approved = dirs
    rows = [cost(1, value=30.0), cost(2, ing="truffle_oil", value=6.0), new_ingredient(3), recipe_line(4, "chicken_wings", 1.25)]
    ap.write(ap.plan(stage(tmp_path, rows, {r.row_id: ("approve",) for r in rows}), synth, approved), approved, NOW)
    con = build(approved, with_approved=True)
    base = build()
    n_costs = base.execute("SELECT COUNT(*) FROM raw_ingredient_costs").fetchone()[0]
    assert con.execute("SELECT unit_cost FROM raw_ingredient_costs WHERE ingredient_id='ribeye' AND effective_week='2025-03-03'").fetchone()[0] == 30.0
    assert con.execute("SELECT COUNT(*) FROM raw_ingredient_costs").fetchone()[0] == n_costs + 1       # one replaced, one new
    assert con.execute("SELECT unit FROM raw_ingredients WHERE ingredient_id='truffle_oil'").fetchone()[0] == "gal"
    assert con.execute("SELECT COUNT(*) FROM raw_recipes WHERE item_id='wings'").fetchall()[0][0] == 1  # replaced all three base lines
    assert con.execute("SELECT qty_per_serving FROM raw_recipes WHERE item_id='wings'").fetchone()[0] == 1.25
    assert con.execute("SELECT COUNT(*) FROM raw_recipes").fetchone()[0] == base.execute("SELECT COUNT(*) FROM raw_recipes").fetchone()[0] - 2


def test_an_existing_ingredient_id_keeps_its_base_row(tmp_path, dirs):
    synth, approved = dirs
    approved.mkdir()
    (approved / "ingredients.csv").write_text("ingredient_id,name,unit\nribeye,Fake Ribeye,gal\n")
    con = build(approved, with_approved=True)
    assert con.execute("SELECT name, unit FROM raw_ingredients WHERE ingredient_id='ribeye'").fetchone() == ("Ribeye steak", "lb")


def test_approved_costs_flow_into_the_simulator_baseline(tmp_path, dirs):
    synth, approved = dirs
    a = cost(1, ing="ribeye", week="2025-12-22", value=30.0)       # the latest week in the data's cost history
    rows = [a]
    ap.write(ap.plan(stage(tmp_path, rows, {a.row_id: ("approve",)}), synth, approved), approved, NOW)
    base, merged = baseline_from_warehouse(build()), baseline_from_warehouse(build(approved, True))
    assert merged["ingredient_costs"]["ribeye"] == 30.0 != base["ingredient_costs"]["ribeye"]
    r0, r1 = run_scenario(base, {}), run_scenario(merged, {})
    assert r1["items"]["ribeye"]["baseline"]["unit_cost"] > r0["items"]["ribeye"]["baseline"]["unit_cost"]


def test_the_pipeline_flag_is_off_by_default():
    import subprocess
    import sys
    out = subprocess.run([sys.executable, "etl/run_pipeline.py", "--help"], cwd=ROOT, capture_output=True, text=True).stdout
    assert "--with-approved" in out and "off by default" in out
