import csv

import pytest

from ingest.stage import (
    COLUMNS,
    FLAGS,
    RunMeta,
    StagedRow,
    make_row_id,
    meta_path,
    read_meta,
    read_staging,
    source_hash,
    sort_rows,
    write_meta,
    write_staging,
)

SHA = source_hash("an invoice")


def cost_row(line, flags=(), **kw):
    return StagedRow.create(make_row_id(SHA, line, "cost"), "cost", flags=flags, ingredient_id="ribeye",
                            effective_week="2025-01-06", unit_cost=22.4, source_line=line, source_quote=f"line {line}", **kw)


def test_closed_vocabularies():
    assert len(FLAGS) == 13 and len(set(FLAGS)) == 13
    with pytest.raises(ValueError, match="closed"):
        StagedRow.create("x", "cost", flags=("made_up",))
    with pytest.raises(ValueError):
        StagedRow("x", "menu_item")
    with pytest.raises(ValueError):
        StagedRow("x", "cost", decision="maybe")


def test_status_is_derived_from_flags():
    assert cost_row(1).status == "proposed"
    assert cost_row(2, flags=("check_failed",)).status == "flagged"
    skipped = StagedRow.create("s", "cost", skipped=True, reason="fuel surcharge", source_line=9)
    assert skipped.status == "skipped" and skipped.flags == ("skipped_line",)
    assert cost_row(3, flags=("conflict", "conflict", "update")).flags == ("conflict", "update")


def test_row_id_is_stable_and_distinguishing():
    assert make_row_id(SHA, 3, "cost") == make_row_id(SHA, 3, "cost")
    assert make_row_id(SHA, 3, "cost") != make_row_id(SHA, 4, "cost")
    assert make_row_id(SHA, 3, "cost") != make_row_id(SHA, 3, "ingredient")
    assert make_row_id(source_hash("another invoice"), 3, "cost") != make_row_id(SHA, 3, "cost")
    assert make_row_id(SHA, 3, "cost", "a") != make_row_id(SHA, 3, "cost", "b")
    assert len(make_row_id(SHA, 1, "cost")) == 12


def test_flagged_rows_sort_first(tmp_path):
    rows = [cost_row(1), cost_row(2, flags=("check_failed",)), StagedRow.create("s", "cost", skipped=True, source_line=0),
            cost_row(3, flags=("update",))]
    assert [r.source_line for r in sort_rows(rows)] == [2, 3, 1, 0]
    p = tmp_path / "run.csv"
    write_staging(rows, p)
    assert [r.status for r in read_staging(p)] == ["flagged", "flagged", "proposed", "skipped"]


def test_columns_and_file_are_plain_csv(tmp_path):
    p = tmp_path / "run.csv"
    write_staging([cost_row(1, flags=("check_failed", "conflict"))], p)
    with open(p, newline="") as f:
        rows = list(csv.reader(f))
    assert tuple(rows[0]) == COLUMNS
    assert rows[1][COLUMNS.index("flags")] == "check_failed;conflict"
    assert rows[1][COLUMNS.index("unit_cost")] == "22.400000"
    assert rows[1][COLUMNS.index("decision")] == ""


def _rewrite(p, edit):
    with open(p, newline="") as f:
        recs = list(csv.DictReader(f))
    edit(recs)
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(recs)


def test_round_trip_with_reviewer_edits(tmp_path):
    p = tmp_path / "run.csv"
    write_staging([cost_row(1), cost_row(2, flags=("check_failed",))], p)  # file order: flagged line 2, then line 1

    def edit(recs):
        by_line = {r["source_line"]: r for r in recs}
        by_line["1"]["decision"] = "Approve"          # reviewers type it in any case
        by_line["2"]["decision"] = "reject"
        by_line["2"]["corrected_value"] = "21.50"

    _rewrite(p, edit)
    back = {r.source_line: r for r in read_staging(p)}
    assert back[1].decision == "approve" and back[2].decision == "reject"
    assert back[2].corrected_value == "21.50"
    assert back[1].unit_cost == pytest.approx(22.4) and back[1].flags == ()
    assert back[2].flags == ("check_failed",)


def test_blank_values_stay_none(tmp_path):
    p = tmp_path / "run.csv"
    write_staging([StagedRow.create("r", "recipe_line", item_id="wings", ingredient_id="chicken_wings", qty_per_serving=1.0)], p)
    back = read_staging(p)[0]
    assert back.unit_cost is None and back.source_line is None and back.qty_per_serving == 1.0


def test_unknown_flag_in_an_edited_file_is_rejected(tmp_path):
    p = tmp_path / "run.csv"
    write_staging([cost_row(1)], p)
    _rewrite(p, lambda recs: recs[0].update(flags="not_a_flag"))
    with pytest.raises(ValueError, match="closed"):
        read_staging(p)


def test_missing_columns_are_reported(tmp_path):
    p = tmp_path / "run.csv"
    p.write_text("row_id,kind\n1,cost\n")
    with pytest.raises(ValueError, match="missing columns"):
        read_staging(p)


def test_writing_is_deterministic(tmp_path):
    rows = [cost_row(i) for i in (3, 1, 2)]
    write_staging(rows, tmp_path / "a.csv")
    write_staging(list(reversed(rows)), tmp_path / "b.csv")
    assert (tmp_path / "a.csv").read_bytes() == (tmp_path / "b.csv").read_bytes()


def test_sidecar_round_trip(tmp_path):
    p = tmp_path / "inv_01.csv"
    meta = RunMeta(kind="invoice", mode="recorded", model="claude-sonnet-5-5", prompt_version="1", schema_version="1",
                   source_file="inv_01.txt", source_sha256=SHA, calls=1, retries=0)
    out = write_meta(meta, p)
    assert out == meta_path(p) == tmp_path / "inv_01.meta.json"
    assert read_meta(p) == meta
    assert out.read_text().startswith("{")
