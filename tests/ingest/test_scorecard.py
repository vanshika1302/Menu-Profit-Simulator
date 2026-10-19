import json
from pathlib import Path

import pytest

from etl.baseline import baseline_from_warehouse
from etl.load import load_all
from etl.warehouse import get_connection
from ingest import scorecard as sc
from ingest.stage import StagedRow

ROOT = Path(__file__).resolve().parents[2]
WEEK = "2025-03-03"


def truth(rows, skipped=(), new=(), kind="invoice", **kw):
    return {"case_id": "t1", "kind": kind, "tier": 1, "split": "dev", "effective_week": WEEK, "rows": rows,
            "skipped": list(skipped), "new_ingredients": list(new), **kw}


def trow(line, ing, cost, flags=()):
    return {"source_line": line, "ingredient_id": ing, "unit_cost": cost, "flags": list(flags)}


def prow(line, ing, cost, flags=(), week=WEEK):
    return StagedRow.create(f"p{line}{ing}", "cost", flags=tuple(flags), ingredient_id=ing, effective_week=week, unit_cost=cost, source_line=line)


def buckets(rows, t):
    return sc.score_case(t, rows)["buckets"]


# ---------------------------------------------------------------- the six buckets
def test_each_bucket_is_counted_once():
    t = truth([trow(1, "ribeye", 22.4), trow(2, "sirloin", 16.0), trow(3, "cream", None, ["unconvertible_unit"]),
               trow(4, "salmon", 14.0), trow(5, "cod", 8.0), trow(6, "bacon", 6.0)])
    rows = [
        prow(1, "ribeye", 22.4),                                     # clean hit
        prow(2, "sirloin", 16.0, ["ambiguous_name"]),                # correct but flagged (over-cautious: truth expects none)
        prow(3, "cream", None, ["unconvertible_unit"]),              # correct and flagged as expected
        prow(4, "salmon", 99.0, ["check_failed"]),                   # wrong, flagged: caught
        prow(5, "cod", 80.0),                                        # wrong, unflagged: silent
        prow(7, "shrimp", 5.0),                                      # no truth row: fabricated (unflagged)
    ]                                                                # bacon is omitted
    b = buckets(rows, t)
    assert b == {"clean_hit": 1, "correct_flagged": 2, "over_cautious": 1, "wrong_flagged": 1, "silent_error": 1,
                 "fabricated": 1, "fabricated_unflagged": 1, "omitted": 1}


def test_headline_rates():
    t = truth([trow(1, "ribeye", 22.4), trow(2, "sirloin", 16.0), trow(3, "salmon", 14.0), trow(4, "cod", 8.0)])
    rows = [prow(1, "ribeye", 22.4), prow(2, "sirloin", 99.0, ["check_failed"]), prow(3, "salmon", 99.0), prow(9, "bacon", 1.0)]
    s = sc.summarise([sc.score_case(t, rows)])
    assert s["rows_produced"] == 4 and s["truth_rows"] == 4
    assert s["silent_error_rate"] == pytest.approx(2 / 4)      # one wrong unflagged row plus one fabricated unflagged row
    assert s["catch_rate"] == pytest.approx(1 / 2)             # of two wrong matched rows, one carried a flag
    assert s["rows"]["precision"] == pytest.approx(1 / 4) and s["rows"]["recall"] == pytest.approx(1 / 4)
    assert s["buckets"]["omitted"] == 1


def test_a_flagged_wrong_row_is_better_than_a_silent_one():
    t = truth([trow(1, "ribeye", 22.4)])
    flagged = sc.summarise([sc.score_case(t, [prow(1, "ribeye", 99.0, ["check_failed"])])])
    silent = sc.summarise([sc.score_case(t, [prow(1, "ribeye", 99.0)])])
    assert flagged["silent_error_rate"] == 0 and flagged["catch_rate"] == 1
    assert silent["silent_error_rate"] == 1 and silent["catch_rate"] == 0


# ---------------------------------------------------------------- tolerance and nulls
@pytest.mark.parametrize("value,ok", [(22.4, True), (22.62, True), (22.63, False), (22.0, False), (0.12, True), (0.13, True), (0.15, False)])
def test_cost_tolerance_is_the_larger_of_one_percent_or_a_cent(value, ok):
    expected = 22.4 if value > 1 else 0.12
    t = truth([trow(1, "ribeye", expected)])
    b = buckets([prow(1, "ribeye", value)], t)
    assert (b.get("clean_hit", 0) == 1) is ok


def test_a_null_truth_needs_a_null_prediction_and_the_reverse():
    t = truth([trow(1, "cream", None, ["unconvertible_unit"])])
    assert buckets([prow(1, "cream", 3.0, ["unconvertible_unit"])], t)["wrong_flagged"] == 1
    t2 = truth([trow(1, "cream", 3.0)])
    assert buckets([prow(1, "cream", None, ["needs_cost"])], t2)["wrong_flagged"] == 1


def test_the_week_is_part_of_the_key():
    t = truth([trow(1, "ribeye", 22.4)])
    b = buckets([prow(1, "ribeye", 22.4, week="2025-02-24")], t)
    assert b["fabricated"] == 1 and b["omitted"] == 1


def test_a_new_ingredient_row_matches_truth_new():
    t = truth([trow(1, "NEW", 6.0, ["new_ingredient"])], new=[{"source_line": 1, "proposed_unit": "gal"}])
    rows = [prow(1, "oil_truffle_black", 6.0, ["new_ingredient"]),
            StagedRow.create("i1", "ingredient", flags=("new_ingredient",), ingredient_id="oil_truffle_black", unit="gal", source_line=1)]
    s = sc.score_case(t, rows)
    assert s["buckets"]["correct_flagged"] == 1 and s["buckets"].get("fabricated", 0) == 0
    assert s["new_ingredients"] == {"tp": 1, "fp": 0, "fn": 0, "unit_ok": 1}
    wrong_unit = [rows[0], StagedRow.create("i1", "ingredient", flags=("new_ingredient",), ingredient_id="x", unit="lb", source_line=1)]
    assert sc.score_case(t, wrong_unit)["new_ingredients"]["unit_ok"] == 0


# ---------------------------------------------------------------- flags and skipped lines
def test_per_flag_precision_and_recall():
    t = truth([trow(1, "cream", None, ["unconvertible_unit"]), trow(2, "flour", 0.8, ["check_failed"]), trow(3, "salmon", 14.0)])
    rows = [prow(1, "cream", None, ["unconvertible_unit"]),         # right flag
            prow(2, "flour", 0.8, ["ambiguous_name"]),              # wrong flag: check_failed missed, ambiguous_name spurious
            prow(3, "salmon", 14.0)]
    s = sc.summarise([sc.score_case(t, rows)])["per_flag"]
    assert s["unconvertible_unit"]["tp"] == 1 and s["unconvertible_unit"]["precision"] == 1 and s["unconvertible_unit"]["recall"] == 1
    assert s["check_failed"]["fn"] == 1 and s["check_failed"]["recall"] == 0
    assert s["ambiguous_name"]["fp"] == 1 and s["ambiguous_name"]["precision"] == 0


def test_skipped_lines_match_on_line_number_and_category():
    t = truth([], skipped=[{"source_line": 9, "category": "fee"}, {"source_line": 10, "category": "credit"}, {"source_line": 11, "category": "discount"}])
    rows = [StagedRow.create("a", "cost", skipped=True, reason="fee", source_line=9),
            StagedRow.create("b", "cost", skipped=True, reason="fee", source_line=10),     # right line, wrong category
            StagedRow.create("c", "cost", skipped=True, reason="fee", source_line=20)]     # spurious
    s = sc.score_case(t, rows)["skipped"]
    assert s == {"tp": 2, "fp": 1, "fn": 1, "category_ok": 1}


def test_skipped_rows_do_not_count_as_produced():
    t = truth([trow(1, "ribeye", 22.4)])
    rows = [prow(1, "ribeye", 22.4), StagedRow.create("a", "cost", skipped=True, reason="fee", source_line=9)]
    assert sc.score_case(t, rows)["produced"] == 1


def test_recipe_lines_match_on_dish_and_ingredient():
    t = {"case_id": "r1", "kind": "recipe", "tier": 1, "split": "dev", "skipped": [], "new_ingredients": [],
         "rows": [{"source_line": 3, "item_id": "wings", "ingredient_id": "chicken_wings", "qty_per_serving": 1.0, "flags": []},
                  {"source_line": 4, "item_id": "wings", "ingredient_id": "hot_sauce", "qty_per_serving": 0.06, "flags": []}]}
    rows = [StagedRow.create("a", "recipe_line", item_id="wings", ingredient_id="chicken_wings", qty_per_serving=1.0, source_line=3),
            StagedRow.create("b", "recipe_line", item_id="wings", ingredient_id="hot_sauce", qty_per_serving=0.12, source_line=4)]
    b = sc.score_case(t, rows)["buckets"]
    assert b["clean_hit"] == 1 and b["silent_error"] == 1


# ---------------------------------------------------------------- a perfect parser, on the real committed truth
def perfect_rows(t):
    """What a perfect parser would stage for a case, built from its truth."""
    rows = []
    kind = "cost" if t["kind"] == "invoice" else "recipe_line"
    for r in t["rows"]:
        flags = tuple(r["flags"])
        ing = "some_new_ingredient" if r["ingredient_id"] == "NEW" else r["ingredient_id"]
        if kind == "cost":
            rows.append(StagedRow.create(f"c{r['source_line']}", "cost", flags=flags, ingredient_id=ing, unit_cost=r["unit_cost"],
                                         effective_week=t["effective_week"] or "", source_line=r["source_line"]))
        else:
            rows.append(StagedRow.create(f"c{r['source_line']}", "recipe_line", flags=flags, item_id=r["item_id"], ingredient_id=ing,
                                         qty_per_serving=r["qty_per_serving"], source_line=r["source_line"]))
    for s in t["skipped"]:
        rows.append(StagedRow.create(f"s{s['source_line']}", kind, skipped=True, reason=s.get("category", s.get("reason", "")), source_line=s["source_line"]))
    for n in t["new_ingredients"]:
        rows.append(StagedRow.create(f"n{n['source_line']}", "ingredient", flags=("new_ingredient",), ingredient_id="some_new_ingredient",
                                     unit=n["proposed_unit"], source_line=n["source_line"]))
    return rows


def test_a_perfect_parser_scores_perfectly_on_every_committed_case():
    cases = sc.load_eval_cases()
    scores, _ = sc.evaluate(cases, lambda c: perfect_rows(c.truth))
    card = sc.scorecard(scores)
    o = card["overall"]
    assert o["cases"] == 60
    assert o["silent_error_rate"] == 0 and o["buckets"]["omitted"] == 0 and o["buckets"]["fabricated"] == 0
    assert o["buckets"]["wrong_flagged"] == 0 and o["buckets"]["silent_error"] == 0
    assert o["rows"]["precision"] == 1 and o["rows"]["recall"] == 1 and o["rows"]["f1"] == 1
    assert all(v["precision"] == 1 and v["recall"] == 1 for v in o["per_flag"].values())
    assert o["skipped_lines"]["fp"] == 0 and o["skipped_lines"]["fn"] == 0 and o["skipped_lines"]["category_ok"] == o["skipped_lines"]["tp"] > 0
    assert o["new_ingredients"]["tp"] == o["new_ingredients"]["unit_ok"] > 0
    assert set(card["by_tier"]) == {"1", "2", "3", "4", "handwritten"} and set(card["by_split"]) == {"dev", "test"}
    assert set(card["by_kind"]) == {"invoice", "recipe"}


def test_splits_are_reported_separately():
    scores, _ = sc.evaluate(sc.load_eval_cases(), lambda c: perfect_rows(c.truth))
    card = sc.scorecard(scores)
    assert card["by_split"]["dev"]["cases"] + card["by_split"]["test"]["cases"] == 60
    assert len(sc.load_eval_cases(split="test")) == card["by_split"]["test"]["cases"]


def test_dropping_every_row_gives_all_omitted():
    scores, _ = sc.evaluate(sc.load_eval_cases(), lambda c: [])
    o = sc.summarise(scores)
    assert o["rows_produced"] == 0 and o["rows"]["recall"] == 0 and o["silent_error_rate"] is None


# ---------------------------------------------------------------- downstream effect
@pytest.fixture(scope="module")
def current_costs():
    con = get_connection(":memory:")
    load_all(con)
    base = baseline_from_warehouse(con)
    con.close()
    return base["ingredient_costs"]


def one_cost_truth(cost):
    return {"c1": {"case_id": "c1", "kind": "invoice", "effective_week": WEEK, "rows": [trow(1, "ribeye", cost)], "skipped": [], "new_ingredients": []}}


def test_a_correct_parse_changes_nothing(current_costs):
    c = current_costs["ribeye"]
    out = sc.downstream_effect({"c1": [prow(1, "ribeye", c)]}, one_cost_truth(c))
    for mode in ("approve_all", "approve_unflagged"):
        assert out[mode]["items_with_cm_error"] == 0 and out[mode]["class_flips"] == 0
        assert out[mode]["weekly_profit_error"] == pytest.approx(0, abs=1e-6)


def test_a_wrong_unflagged_row_flips_classes_in_both_approval_modes(current_costs):
    c = current_costs["ribeye"]
    out = sc.downstream_effect({"c1": [prow(1, "ribeye", c * 5)]}, one_cost_truth(c))
    for mode in ("approve_all", "approve_unflagged"):
        assert out[mode]["items_with_cm_error"] >= 1 and out[mode]["max_abs_cm_error"] > 50
        assert out[mode]["class_flips"] >= 1 and "ribeye" in out[mode]["flipped_items"]
        assert out[mode]["weekly_profit_error"] < 0


def test_the_same_wrong_row_flagged_only_hurts_if_everything_is_approved(current_costs):
    c = current_costs["ribeye"]
    rows = {"c1": [prow(1, "ribeye", c * 5, ["check_failed"])]}
    out = sc.downstream_effect(rows, one_cost_truth(c))
    assert out["approve_all"]["class_flips"] >= 1                        # a reviewer who approves everything is hurt
    assert out["approve_unflagged"]["class_flips"] == 0                  # one who skips flagged rows is not
    assert out["approve_unflagged"]["items_with_cm_error"] == 0


def test_recipe_errors_move_costs_too(current_costs):
    t = {"r1": {"case_id": "r1", "kind": "recipe", "effective_week": None, "skipped": [], "new_ingredients": [],
                "rows": [{"source_line": 3, "item_id": "ribeye", "ingredient_id": "ribeye", "qty_per_serving": 0.625, "flags": []},
                         {"source_line": 4, "item_id": "ribeye", "ingredient_id": "potato", "qty_per_serving": 0.4, "flags": []},
                         {"source_line": 5, "item_id": "ribeye", "ingredient_id": "butter", "qty_per_serving": 0.06, "flags": []},
                         {"source_line": 6, "item_id": "ribeye", "ingredient_id": "mixed_greens", "qty_per_serving": 0.1, "flags": []}]}}
    good = [StagedRow.create(f"g{i}", "recipe_line", item_id="ribeye", ingredient_id=r["ingredient_id"], qty_per_serving=r["qty_per_serving"], source_line=i)
            for i, r in enumerate(t["r1"]["rows"], 3)]
    assert sc.downstream_effect({"r1": good}, t)["approve_all"]["items_with_cm_error"] == 0
    bad = [StagedRow.create(g.row_id, "recipe_line", item_id="ribeye", ingredient_id=g.ingredient_id,
                            qty_per_serving=g.qty_per_serving * (3 if g.ingredient_id == "ribeye" else 1), source_line=g.source_line) for g in good]
    out = sc.downstream_effect({"r1": bad}, t)["approve_all"]
    assert out["items_with_cm_error"] == 1 and out["max_abs_cm_error"] > 20
    assert "ribeye" in out["flipped_items"]          # and a neighbour can flip too, because the category thresholds move


def test_the_scorecard_does_not_touch_sim_or_the_committed_data():
    before = {p.name: p.read_bytes() for p in (ROOT / "data" / "synthetic").glob("*.csv")}
    sc.downstream_effect({"c1": [prow(1, "ribeye", 100.0)]}, one_cost_truth(21.0))
    assert before == {p.name: p.read_bytes() for p in (ROOT / "data" / "synthetic").glob("*.csv")}
