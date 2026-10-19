"""Review step: turn a reviewed staging file into the approved overlay.

A person edits `decision` (approve or reject) and optionally `corrected_value` in the staging CSV;
`plan` validates it and `write` applies it. Nothing is written unless `write` is called, a blank
decision means no change, and there is no bulk-approval path. Approved rows go to `data/approved/`
(never to the generator-owned `data/synthetic/`); `etl/load.py` merges them only when asked.
"""
from __future__ import annotations

import csv
import dataclasses
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ingest.stage import StagedRow, read_meta, read_staging, source_hash
from ingest.units import INGREDIENT_UNITS

ROOT = Path(__file__).resolve().parents[1]
APPROVED_DIR = ROOT / "data" / "approved"
SYNTH_DIR = ROOT / "data" / "synthetic"

OVERLAY_COLUMNS = {
    "ingredients": ["ingredient_id", "name", "unit"],
    "recipes": ["item_id", "ingredient_id", "qty_per_serving"],
    "ingredient_costs": ["ingredient_id", "effective_week", "unit_cost"],
}
LOG_COLUMNS = ["run_id", "row_id", "kind", "key", "decision", "approved_at", "source_sha256", "original_value",
               "corrected_value", "flags"]
CORRECTABLE = {"unit_cost", "qty_per_serving", "ingredient_id", "effective_week", "unit", "name"}


class ApplyError(Exception):
    """A reviewed file has a problem a person must fix before anything is written."""


@dataclass
class Action:
    row: StagedRow
    decision: str               # "approve" | "reject"
    values: dict                # final field values after any correction
    original: str
    corrected: str
    edited: bool
    key: str
    replaces: str = ""          # description of what an approval would replace


@dataclass
class Plan:
    run_id: str
    source_sha256: str
    actions: list[Action] = field(default_factory=list)
    already_applied: list[str] = field(default_factory=list)
    untouched: int = 0
    errors: list[str] = field(default_factory=list)
    recipe_notes: list[str] = field(default_factory=list)

    @property
    def approvals(self) -> list[Action]:
        return [a for a in self.actions if a.decision == "approve"]

    def describe(self) -> str:
        lines = [f"run {self.run_id}: {len(self.approvals)} to approve, "
                 f"{sum(a.decision == 'reject' for a in self.actions)} to reject, {self.untouched} undecided (no change), "
                 f"{len(self.already_applied)} already applied"]
        for a in self.actions:
            sign = "+" if a.decision == "approve" else "x"
            tag = " [edited]" if a.edited else ""
            lines.append(f"  {sign} {a.row.kind:<11} {a.key}  {_show(a.values)}{tag}" + (f"  ({a.replaces})" if a.replaces else ""))
        lines += [f"  note: {n}" for n in self.recipe_notes]
        lines += [f"  ERROR: {e}" for e in self.errors]
        return "\n".join(lines)


def _show(values: dict) -> str:
    return ", ".join(f"{k}={v}" for k, v in values.items() if v not in ("", None))


# ------------------------------------------------------------------ reading existing files
def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def known_context(synth_dir: Path, approved_dir: Path) -> dict:
    ings = {r["ingredient_id"] for r in _read_csv(Path(synth_dir) / "ingredients.csv")}
    ings |= {r["ingredient_id"] for r in _read_csv(Path(approved_dir) / "ingredients.csv")}
    items = {r["item_id"] for r in _read_csv(Path(synth_dir) / "menu_items.csv")}
    base_costs = {(r["ingredient_id"], r["effective_week"]): r["unit_cost"] for r in _read_csv(Path(synth_dir) / "ingredient_costs.csv")}
    base_costs.update({(r["ingredient_id"], r["effective_week"]): r["unit_cost"] for r in _read_csv(Path(approved_dir) / "ingredient_costs.csv")})
    base_recipes: dict[str, int] = {}
    for r in _read_csv(Path(synth_dir) / "recipes.csv"):
        base_recipes[r["item_id"]] = base_recipes.get(r["item_id"], 0) + 1
    return {"ingredients": ings, "items": items, "costs": base_costs, "recipe_lines": base_recipes}


# ------------------------------------------------------------------ planning
def _parse_correction(row: StagedRow) -> dict:
    """`corrected_value` is a bare number (the row's value) or `field=value` pairs separated by ';'."""
    text = row.corrected_value.strip()
    if not text:
        return {}
    out: dict = {}
    for part in (p.strip() for p in text.split(";") if p.strip()):
        if "=" in part:
            k, v = (x.strip() for x in part.split("=", 1))
        else:
            k, v = {"cost": "unit_cost", "recipe_line": "qty_per_serving", "ingredient": "unit"}[row.kind], part
        if k not in CORRECTABLE:
            raise ApplyError(f"row {row.row_id}: cannot correct {k!r}; allowed: {sorted(CORRECTABLE)}")
        out[k] = v
    return out


def _number(row: StagedRow, name: str, value) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ApplyError(f"row {row.row_id}: {name} {value!r} is not a number") from None
    if v <= 0:
        raise ApplyError(f"row {row.row_id}: {name} must be positive, got {v}")
    return v


def plan(staging_path: Path, synth_dir: Path = SYNTH_DIR, approved_dir: Path = APPROVED_DIR) -> Plan:
    staging_path = Path(staging_path)
    rows = read_staging(staging_path)
    try:
        meta = read_meta(staging_path)
        source_sha, run_id = meta.source_sha256, meta.source_sha256[:12]
    except FileNotFoundError:
        source_sha = source_hash(staging_path.read_text())
        run_id = source_sha[:12]
    ctx = known_context(synth_dir, approved_dir)
    logged = {r["row_id"] for r in _read_csv(Path(approved_dir) / "approvals.csv")}
    p = Plan(run_id=run_id, source_sha256=source_sha)

    # ingredients proposed in this file and approved are valid targets for the other rows of the same file
    approved_new = {r.ingredient_id for r in rows if r.kind == "ingredient" and r.decision == "approve"}
    valid_ingredients = ctx["ingredients"] | approved_new

    for r in rows:
        if r.decision == "":
            p.untouched += 1
            continue
        if r.row_id in logged:
            p.already_applied.append(r.row_id)
            continue
        try:
            corr = _parse_correction(r)
            if r.decision == "reject":
                p.actions.append(Action(r, "reject", {}, "", r.corrected_value, False, _key(r, {})))
                continue
            if r.status == "skipped":
                raise ApplyError(f"row {r.row_id}: a skipped line has nothing to apply; reject it or leave the decision blank")
            vals = _final_values(r, corr)
            _validate(r, vals, valid_ingredients, ctx)
            edited = bool(corr)
            key = _key(r, vals)
            replaces = _replaces(r, vals, ctx)
            p.actions.append(Action(r, "approve", vals, _original(r), r.corrected_value, edited, key, replaces))
        except ApplyError as e:
            p.errors.append(str(e))

    # an approved recipe replaces every row for its dish: say how many it replaces
    by_dish: dict[str, int] = {}
    for a in p.approvals:
        if a.row.kind == "recipe_line":
            by_dish[a.values["item_id"]] = by_dish.get(a.values["item_id"], 0) + 1
    for dish, n in sorted(by_dish.items()):
        existing = ctx["recipe_lines"].get(dish, 0)
        if existing:
            p.recipe_notes.append(f"approving {n} line(s) for {dish} replaces all {existing} existing recipe line(s) for that dish")
    return p


def _key(r: StagedRow, vals: dict) -> str:
    v = vals or {}
    if r.kind == "cost":
        return f"{v.get('ingredient_id') or r.ingredient_id} @ {v.get('effective_week') or r.effective_week}"
    if r.kind == "recipe_line":
        return f"{v.get('item_id') or r.item_id} / {v.get('ingredient_id') or r.ingredient_id}"
    return v.get("ingredient_id") or r.ingredient_id


def _original(r: StagedRow) -> str:
    if r.kind == "cost":
        return "" if r.unit_cost is None else f"{r.unit_cost:.6f}"
    if r.kind == "recipe_line":
        return "" if r.qty_per_serving is None else f"{r.qty_per_serving:.6f}"
    return r.unit


def _final_values(r: StagedRow, corr: dict) -> dict:
    if r.kind == "cost":
        return {"ingredient_id": corr.get("ingredient_id", r.ingredient_id), "effective_week": corr.get("effective_week", r.effective_week),
                "unit_cost": corr.get("unit_cost", r.unit_cost)}
    if r.kind == "recipe_line":
        return {"item_id": r.item_id, "ingredient_id": corr.get("ingredient_id", r.ingredient_id),
                "qty_per_serving": corr.get("qty_per_serving", r.qty_per_serving)}
    return {"ingredient_id": corr.get("ingredient_id", r.ingredient_id), "name": corr.get("name", r.name), "unit": corr.get("unit", r.unit)}


def _validate(r: StagedRow, vals: dict, valid_ingredients: set, ctx: dict) -> None:
    """Re-check a (possibly corrected) row: the ingredient exists, numbers are positive, the unit is allowed."""
    if r.kind == "cost":
        if vals["ingredient_id"] not in valid_ingredients:
            raise ApplyError(f"row {r.row_id}: ingredient {vals['ingredient_id']!r} is not in the catalogue")
        if not vals["effective_week"]:
            raise ApplyError(f"row {r.row_id}: no effective week; correct it with effective_week=YYYY-MM-DD (a Monday)")
        try:
            wk = datetime.strptime(vals["effective_week"], "%Y-%m-%d").date()
        except ValueError:
            raise ApplyError(f"row {r.row_id}: effective week {vals['effective_week']!r} is not a date") from None
        if wk.weekday() != 0:
            raise ApplyError(f"row {r.row_id}: effective week {wk} is not a Monday")
        if vals["unit_cost"] is None:
            raise ApplyError(f"row {r.row_id}: this row has no cost; give a corrected_value or reject it")
        vals["unit_cost"] = _number(r, "unit_cost", vals["unit_cost"])
    elif r.kind == "recipe_line":
        if vals["item_id"] not in ctx["items"]:
            raise ApplyError(f"row {r.row_id}: dish {vals['item_id']!r} is not a menu item")
        if vals["ingredient_id"] not in valid_ingredients:
            raise ApplyError(f"row {r.row_id}: ingredient {vals['ingredient_id']!r} is not in the catalogue")
        if vals["qty_per_serving"] is None:
            raise ApplyError(f"row {r.row_id}: this row has no quantity; give a corrected_value or reject it")
        vals["qty_per_serving"] = _number(r, "qty_per_serving", vals["qty_per_serving"])
    else:
        if not vals["ingredient_id"] or not vals["name"]:
            raise ApplyError(f"row {r.row_id}: a new ingredient needs an id and a name")
        if vals["unit"] not in INGREDIENT_UNITS:
            raise ApplyError(f"row {r.row_id}: unit {vals['unit']!r} must be one of {INGREDIENT_UNITS}")


def _replaces(r: StagedRow, vals: dict, ctx: dict) -> str:
    if r.kind == "cost":
        old = ctx["costs"].get((vals["ingredient_id"], vals["effective_week"]))
        if old is not None:
            return f"replaces {float(old):.4f}"
    if r.kind == "ingredient" and vals["ingredient_id"] in ctx["ingredients"]:
        return "already exists: the existing ingredient is kept"
    return ""


# ------------------------------------------------------------------ writing
def write(p: Plan, approved_dir: Path = APPROVED_DIR, now: datetime | None = None) -> None:
    """Apply an error-free plan: update the overlay CSVs and append to the approval log."""
    if p.errors:
        raise ApplyError("fix these before writing:\n" + "\n".join(p.errors))
    approved_dir = Path(approved_dir)
    now = now or datetime.now(timezone.utc)
    files = {name: _read_csv(approved_dir / f"{name}.csv") for name in OVERLAY_COLUMNS}

    new_ings = [a for a in p.approvals if a.row.kind == "ingredient"]
    have = {r["ingredient_id"] for r in files["ingredients"]}
    for a in new_ings:
        if a.values["ingredient_id"] not in have:
            files["ingredients"].append({k: a.values[k] for k in OVERLAY_COLUMNS["ingredients"]})
            have.add(a.values["ingredient_id"])

    for a in (x for x in p.approvals if x.row.kind == "cost"):  # a later run beats an earlier one for the same key
        v = a.values
        files["ingredient_costs"] = [r for r in files["ingredient_costs"]
                                     if (r["ingredient_id"], r["effective_week"]) != (v["ingredient_id"], v["effective_week"])]
        files["ingredient_costs"].append({"ingredient_id": v["ingredient_id"], "effective_week": v["effective_week"], "unit_cost": f"{v['unit_cost']:.6f}"})

    dishes = {a.values["item_id"] for a in p.approvals if a.row.kind == "recipe_line"}
    if dishes:  # an approved recipe replaces every earlier row for its dish
        files["recipes"] = [r for r in files["recipes"] if r["item_id"] not in dishes]
        for a in (x for x in p.approvals if x.row.kind == "recipe_line"):
            v = a.values
            files["recipes"].append({"item_id": v["item_id"], "ingredient_id": v["ingredient_id"], "qty_per_serving": f"{v['qty_per_serving']:.6f}"})

    for name, rows in files.items():
        if rows or (approved_dir / f"{name}.csv").exists():
            _write_csv(approved_dir / f"{name}.csv", OVERLAY_COLUMNS[name], rows)

    log_path = approved_dir / "approvals.csv"
    log = _read_csv(log_path)
    for a in p.actions:
        flags = list(a.row.flags) + (["edited"] if a.edited and "edited" not in a.row.flags else [])
        log.append({"run_id": p.run_id, "row_id": a.row.row_id, "kind": a.row.kind, "key": a.key, "decision": a.decision,
                    "approved_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "source_sha256": p.source_sha256,
                    "original_value": a.original, "corrected_value": a.corrected, "flags": ";".join(flags)})
    _write_csv(log_path, LOG_COLUMNS, log)
