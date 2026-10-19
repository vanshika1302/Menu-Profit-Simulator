"""Score the parser against the evaluation set's truth, including the effect on the simulator's answers.

Rows match on keys: invoice cost rows on (ingredient, week), recipe lines on (dish, ingredient), skipped
lines on their line number. A predicted row with no truth row is **fabricated**; a truth row with no
prediction is **omitted**. Every produced row falls in one bucket:

    clean_hit          correct and unflagged
    correct_flagged    correct but flagged (some of it over-cautious: the truth expected no flag)
    wrong_flagged      wrong value, flagged: the error was caught
    silent_error       wrong value, unflagged: the costly one
    fabricated         no truth row (counted silent when unflagged)
    omitted            a truth row with no prediction

Headline numbers are the silent error rate and the catch rate. No pass/fail bounds on any finding.
The downstream effect is this project's own method (no published standard exists): apply the parsed rows as an
overlay, rebuild the baseline, and compare with the baseline built from the true rows.
"""
from __future__ import annotations

import collections
import csv
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ingest.apply import OVERLAY_COLUMNS
from ingest.stage import StagedRow

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "data" / "eval"
SYNTH_DIR = ROOT / "data" / "synthetic"

COST_ABS, VALUE_REL, QTY_ABS = 0.01, 0.01, 0.001
IGNORED_FLAGS = {"skipped_line", "update", "edited"}  # context-dependent or added later by a person


@dataclass
class EvalCase:
    truth: dict
    text: str

    @property
    def case_id(self) -> str:
        return self.truth["case_id"]


def load_eval_cases(eval_dir: Path = EVAL_DIR, split: str | None = None) -> list[EvalCase]:
    cases = []
    for p in sorted((Path(eval_dir) / "truth").glob("*.json")):
        t = json.loads(p.read_text())
        if split and t["split"] != split:
            continue
        cases.append(EvalCase(t, (Path(eval_dir) / t["source_file"]).read_text()))
    return cases


# ------------------------------------------------------------------ matching one case
def _value_ok(kind: str, predicted, expected) -> bool:
    if expected is None or predicted is None:
        return expected is None and predicted is None
    tol = max(COST_ABS if kind == "cost" else QTY_ABS, VALUE_REL * abs(expected))
    return abs(predicted - expected) <= tol + 1e-9


def _predicted_key(row: StagedRow, kind: str) -> tuple:
    ing = "NEW" if "new_ingredient" in row.flags else row.ingredient_id
    return (ing, row.effective_week) if kind == "cost" else (row.item_id, ing)


def _flags(row_flags) -> set[str]:
    return set(row_flags) - IGNORED_FLAGS


def score_case(truth: dict, rows: list[StagedRow]) -> dict:
    """Bucket counts and detail for one document."""
    kind = "cost" if truth["kind"] == "invoice" else "recipe_line"
    value_field = "unit_cost" if kind == "cost" else "qty_per_serving"
    week = truth.get("effective_week") or ""
    truth_rows = {}
    for r in truth["rows"]:
        k = (r["ingredient_id"], week) if kind == "cost" else (r["item_id"], r["ingredient_id"])
        truth_rows[k] = r
    produced = [r for r in rows if r.kind == kind and r.status != "skipped"]
    skipped = [r for r in rows if r.status == "skipped"]
    ingredient_rows = [r for r in rows if r.kind == "ingredient"]

    b = collections.Counter()
    per_flag = collections.defaultdict(collections.Counter)
    details = []
    matched_keys = set()

    for r in produced:
        k = _predicted_key(r, kind)
        flagged = bool(_flags(r.flags))
        tr = truth_rows.get(k)
        if tr is None:
            b["fabricated"] += 1
            b["fabricated_unflagged"] += (not flagged)
            for f in _flags(r.flags):
                per_flag[f]["fp"] += 1
            details.append({"bucket": "fabricated", "key": k, "source_line": r.source_line})
            continue
        matched_keys.add(k)
        correct = _value_ok(kind, getattr(r, value_field), tr[value_field])
        if correct and not flagged:
            bucket = "clean_hit"
        elif correct:
            bucket = "correct_flagged"
            b["over_cautious"] += (not _flags(tr["flags"]))
        elif flagged:
            bucket = "wrong_flagged"
        else:
            bucket = "silent_error"
        b[bucket] += 1
        got, want = _flags(r.flags), _flags(tr["flags"])
        for f in got | want:
            per_flag[f]["tp" if f in got and f in want else "fp" if f in got else "fn"] += 1
        details.append({"bucket": bucket, "key": k, "source_line": r.source_line, "truth_value": tr[value_field], "value": getattr(r, value_field)})

    for k, tr in truth_rows.items():
        if k not in matched_keys:
            b["omitted"] += 1
            for f in _flags(tr["flags"]):
                per_flag[f]["fn"] += 1
            details.append({"bucket": "omitted", "key": k, "source_line": tr["source_line"]})

    # skipped lines (fees, credits, "to taste") match on line number
    t_skip = {s["source_line"]: s for s in truth.get("skipped", [])}
    p_skip = {r.source_line: r for r in skipped}
    skip = {"tp": 0, "fp": 0, "fn": 0, "category_ok": 0}
    for line, r in p_skip.items():
        if line in t_skip:
            skip["tp"] += 1
            want = t_skip[line].get("category")
            skip["category_ok"] += (want is None or r.reason == want)
        else:
            skip["fp"] += 1
    skip["fn"] = len([line for line in t_skip if line not in p_skip])

    # new ingredients match on line number; correct if the proposed unit is right
    t_new = {n["source_line"]: n for n in truth.get("new_ingredients", [])}
    p_new = {r.source_line: r for r in ingredient_rows}
    new = {"tp": 0, "fp": 0, "fn": 0, "unit_ok": 0}
    for line, r in p_new.items():
        if line in t_new:
            new["tp"] += 1
            new["unit_ok"] += (r.unit == t_new[line].get("proposed_unit"))
        else:
            new["fp"] += 1
    new["fn"] = len([line for line in t_new if line not in p_new])

    return {"case_id": truth["case_id"], "kind": truth["kind"], "tier": truth["tier"], "split": truth.get("split"),
            "produced": len(produced), "truth_rows": len(truth_rows), "buckets": dict(b),
            "flags": {f: dict(c) for f, c in per_flag.items()}, "skipped": skip, "new_ingredients": new, "details": details}


# ------------------------------------------------------------------ aggregate
def _sum(case_scores: list[dict]) -> dict:
    b = collections.Counter()
    flags = collections.defaultdict(collections.Counter)
    skip, new = collections.Counter(), collections.Counter()
    produced = truth_rows = 0
    for c in case_scores:
        b.update(c["buckets"])
        produced += c["produced"]
        truth_rows += c["truth_rows"]
        skip.update(c["skipped"])
        new.update(c["new_ingredients"])
        for f, cnt in c["flags"].items():
            flags[f].update(cnt)
    return {"b": b, "flags": flags, "skip": skip, "new": new, "produced": produced, "truth_rows": truth_rows}


def _prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f = 2 * p * r / (p + r) if p and r else (0.0 if p is not None and r is not None else None)
    return {"precision": p, "recall": r, "f1": f}


def summarise(case_scores: list[dict]) -> dict:
    """Row-level F1, the six buckets, the two headline rates, and per-flag, skipped-line and new-ingredient scores."""
    s = _sum(case_scores)
    b = s["b"]
    correct = b["clean_hit"] + b["correct_flagged"]
    wrong_matched = b["wrong_flagged"] + b["silent_error"]
    silent = b["silent_error"] + b["fabricated_unflagged"]
    produced = s["produced"]
    out = {
        "cases": len(case_scores), "rows_produced": produced, "truth_rows": s["truth_rows"],
        "buckets": {k: b[k] for k in ("clean_hit", "correct_flagged", "wrong_flagged", "silent_error", "fabricated", "omitted")},
        "over_cautious": b["over_cautious"],
        "rows": _prf(correct, produced - correct, s["truth_rows"] - correct),
        "silent_error_rate": silent / produced if produced else None,
        "catch_rate": (b["wrong_flagged"] / wrong_matched) if wrong_matched else None,
        "per_flag": {f: {**c, **_prf(c["tp"], c["fp"], c["fn"])} for f, c in sorted(
            ((f, {k: s["flags"][f][k] for k in ("tp", "fp", "fn")}) for f in s["flags"]))},
        "skipped_lines": {**{k: s["skip"][k] for k in ("tp", "fp", "fn", "category_ok")}, **_prf(s["skip"]["tp"], s["skip"]["fp"], s["skip"]["fn"])},
        "new_ingredients": {**{k: s["new"][k] for k in ("tp", "fp", "fn", "unit_ok")}, **_prf(s["new"]["tp"], s["new"]["fp"], s["new"]["fn"])},
    }
    return out


def scorecard(case_scores: list[dict]) -> dict:
    """Overall, per tier, per kind and per split."""
    out = {"overall": summarise(case_scores), "by_tier": {}, "by_kind": {}, "by_split": {}}
    for field_, key in (("tier", "by_tier"), ("kind", "by_kind"), ("split", "by_split")):
        groups = collections.defaultdict(list)
        for c in case_scores:
            groups[str(c[field_])].append(c)
        out[key] = {g: summarise(v) for g, v in sorted(groups.items())}
    return out


def evaluate(cases: list[EvalCase], parse_fn: Callable[[EvalCase], list[StagedRow]]) -> tuple[list[dict], dict]:
    """Run `parse_fn(case) -> rows` over the cases. Returns (per-case scores, rows by case id)."""
    scores, rows_by_case = [], {}
    for case in cases:
        rows = parse_fn(case)
        rows_by_case[case.case_id] = rows
        scores.append(score_case(case.truth, rows))
    return scores, rows_by_case


# ------------------------------------------------------------------ downstream effect
def _write_overlay(directory: Path, costs: dict, recipes: dict, ingredients: list[dict]) -> None:
    directory.mkdir(parents=True, exist_ok=True)

    def write(name, rows):
        with open(directory / f"{name}.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=OVERLAY_COLUMNS[name], lineterminator="\n")
            w.writeheader()
            w.writerows(rows)

    write("ingredients", ingredients)
    write("ingredient_costs", [{"ingredient_id": i, "effective_week": wk, "unit_cost": v} for (i, wk), v in costs.items()])
    write("recipes", [{"item_id": d, "ingredient_id": i, "qty_per_serving": q} for d, lines in recipes.items() for i, q in lines.items()])


def _latest_week(synth_dir: Path) -> str:
    with open(Path(synth_dir) / "ingredient_costs.csv", newline="") as f:
        return max(r["effective_week"] for r in csv.DictReader(f))


def _parsed_overlay(rows_by_case: dict[str, list[StagedRow]], mode: str, week: str):
    """Costs, recipes and new ingredients from parsed rows. `mode` is 'all' (approve every row that has a
    value) or 'unflagged' (only rows that are proposed with no flags). Every cost is placed in `week`, the
    latest cost week: each invoice is treated as the current cost evidence."""
    costs, recipes, ings = {}, {}, []
    for case_id in sorted(rows_by_case):
        dishes: dict[str, dict] = {}
        for r in rows_by_case[case_id]:
            if r.status == "skipped":
                continue
            if mode == "unflagged" and (r.status != "proposed" or r.flags):
                continue
            if r.kind == "ingredient":
                ings.append({"ingredient_id": r.ingredient_id, "name": r.name, "unit": r.unit})
            elif r.kind == "cost" and r.unit_cost is not None and r.ingredient_id:
                costs[(r.ingredient_id, week)] = r.unit_cost
            elif r.kind == "recipe_line" and r.qty_per_serving is not None and r.item_id and r.ingredient_id:
                dishes.setdefault(r.item_id, {})[r.ingredient_id] = r.qty_per_serving
        recipes.update(dishes)
    return costs, recipes, ings


def _true_overlay(cases: dict[str, dict], week: str):
    costs, recipes = {}, {}
    for case_id in sorted(cases):
        t = cases[case_id]
        for r in t["rows"]:
            if t["kind"] == "invoice":
                if r["unit_cost"] is not None and r["ingredient_id"] != "NEW":
                    costs[(r["ingredient_id"], week)] = r["unit_cost"]
            elif r["qty_per_serving"] is not None:
                recipes.setdefault(r["item_id"], {})[r["ingredient_id"]] = r["qty_per_serving"]
    return costs, recipes, []


def _baseline_with(overlay, synth_dir: Path):
    from etl.baseline import baseline_from_warehouse
    from etl.load import load_all
    from etl.warehouse import get_connection
    from sim.scenarios import run_scenario

    costs, recipes, ings = overlay
    with tempfile.TemporaryDirectory() as tmp:
        _write_overlay(Path(tmp), costs, recipes, ings)
        con = get_connection(":memory:")
        load_all(con, Path(synth_dir), with_approved=True, approved_dir=Path(tmp))
        base = baseline_from_warehouse(con)
        con.close()
    return base, run_scenario(base, {})


def downstream_effect(rows_by_case: dict[str, list[StagedRow]], truths: dict[str, dict], synth_dir: Path = SYNTH_DIR) -> dict:
    """Cost, margin, total weekly profit and menu-class changes the parsed rows would cause, against the
    baseline built from the true rows, approving every row and approving only unflagged rows."""
    week = _latest_week(synth_dir)
    truth_base, truth_run = _baseline_with(_true_overlay(truths, week), synth_dir)
    out = {}
    for mode, name in (("all", "approve_all"), ("unflagged", "approve_unflagged")):
        base, run = _baseline_with(_parsed_overlay(rows_by_case, mode, week), synth_dir)
        cm_err, changed, flips = [], [], []
        for i, row in run["items"].items():
            t = truth_run["items"][i]
            d = row["baseline"]["cm"] - t["baseline"]["cm"]
            if abs(d) > 0.005:
                changed.append(i)
                cm_err.append(abs(d))
            if row["matrix"]["baseline_class"] != t["matrix"]["baseline_class"]:
                flips.append(i)
        out[name] = {
            "items_with_cm_error": len(changed),
            "mean_abs_cm_error": sum(cm_err) / len(cm_err) if cm_err else 0.0,
            "max_abs_cm_error": max(cm_err) if cm_err else 0.0,
            "weekly_profit_error": run["total"]["baseline"]["profit"] - truth_run["total"]["baseline"]["profit"],
            "class_flips": len(flips), "flipped_items": sorted(flips),
        }
    return out
