"""Parse pipeline: a document's text to staged rows.

The model copies raw strings and a source quote; this module does everything else: validates the
output, checks every quote against the source text, retries once on semantic failures, converts
units and computes costs in code, maps names, sets the effective week, lists skipped lines,
detects conflicts and updates, and builds the staged rows. Nothing is silently dropped: a line
that cannot be costed becomes a flagged row with no value.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from fractions import Fraction
from pathlib import Path

from ingest import model_client as mc
from ingest.normalise import (
    Range,
    amount_in,
    check_line_total,
    pack_quantity,
    parse_amount,
    parse_date,
    parse_number,
    parse_pack,
    parse_price,
    parse_quantity,
    unit_cost_catch_weight,
    unit_cost_from_case,
    unit_cost_from_unit_price,
    week_monday,
)
from ingest.stage import RunMeta, StagedRow, make_row_id, source_hash
from ingest.units import UNITS, convert, dimension, is_refusal, normalise_unit

CASE_WORDS = {"cs", "case", "cases", "bx", "box"}
CATCH_WORDS = {"cw", "c/w", "catch weight", "catchweight"}
YIELD_WORDS = re.compile(r"\b(yield|trim|trimmed|trimming|edible|peeled|cooked|as purchased|\bEP\b|\bAP\b)\b", re.I)
DEFAULT_UNIT_BY_DIMENSION = {"weight": "lb", "volume": "gal", "count": "each"}


# ------------------------------------------------------------------ context
@dataclass
class Catalogue:
    """What the parser knows about the restaurant: ingredients, menu items, and existing rows."""

    ingredients: dict[str, dict]            # ingredient_id -> {"name", "unit"}
    items: dict[str, str]                   # item_id -> name
    existing_costs: dict[tuple[str, str], float] = field(default_factory=dict)   # (ingredient_id, week) -> unit_cost
    existing_recipes: set[str] = field(default_factory=set)                        # item_ids that already have recipe rows

    def ingredient_context(self) -> str:
        rows = "\n".join(f"{i} | {v['name']} | {v['unit']}" for i, v in sorted(self.ingredients.items()))
        return f"Ingredient catalogue (ingredient_id | name | unit):\n{rows}"

    def recipe_context(self) -> str:
        items = "\n".join(f"{i} | {n}" for i, n in sorted(self.items.items()))
        return f"Menu items (item_id | name):\n{items}\n\n{self.ingredient_context()}"


def load_catalogue(data_dir: Path, with_existing: bool = True) -> Catalogue:
    import csv

    ings = {r["ingredient_id"]: {"name": r["name"], "unit": r["unit"]} for r in csv.DictReader(open(Path(data_dir) / "ingredients.csv"))}
    items = {r["item_id"]: r["name"] for r in csv.DictReader(open(Path(data_dir) / "menu_items.csv"))}
    cat = Catalogue(ings, items)
    if with_existing:
        cat.existing_costs = {(r["ingredient_id"], r["effective_week"]): float(r["unit_cost"])
                              for r in csv.DictReader(open(Path(data_dir) / "ingredient_costs.csv"))}
        cat.existing_recipes = {r["item_id"] for r in csv.DictReader(open(Path(data_dir) / "recipes.csv"))}
    return cat


@dataclass
class ParseResult:
    rows: list[StagedRow]
    meta: RunMeta
    errors: list[str] = field(default_factory=list)


# ------------------------------------------------------------------ text checks
def norm(text: str) -> str:
    return " ".join(text.split()).lower()


def locate(quote: str, doc_lines: list[str]) -> int | None:
    """1-based line number of the first line containing the quote (whitespace-normalised), else None.
    A quote spanning lines is searched in the joined text and reported at its first line."""
    q = norm(quote)
    if not q:
        return None
    for i, line in enumerate(doc_lines, 1):
        if q in norm(line):
            return i
    joined = norm(" ".join(doc_lines))
    if q in joined:
        first = q.split(" ")[0]
        for i, line in enumerate(doc_lines, 1):
            if first in norm(line):
                return i
    return None


def _safe_price(text):
    if text is None or not str(text).strip():
        return None
    v = parse_price(str(text))
    return None if is_refusal(v) else v


def _case_word(text: str | None) -> bool:
    return bool(text) and text.strip().lower().rstrip(".") in CASE_WORDS


# ------------------------------------------------------------------ line cost (invoice)
@dataclass
class LineCost:
    unit_cost: float | None
    quantity: float | None            # total received or ordered, in the ingredient's unit (for weighting)
    flags: list[str]
    reason: str


def compute_line_cost(line: dict, to_unit: str) -> LineCost:
    """The ticket-03 rules for one invoice line. A refusal gives no value and the matching flag."""
    flags: list[str] = []
    pack_text = (line.get("pack_text") or "").strip()
    unit_price = _safe_price(line.get("unit_price"))
    ext = _safe_price(line.get("extended_price"))
    price_unit_text = (line.get("price_unit_text") or "").strip() or None
    unit_text = (line.get("unit_text") or "").strip() or None
    catch_weight = pack_text.lower() in CATCH_WORDS or (bool(line.get("qty_received")) and not pack_text)

    def refuse(r) -> LineCost:
        return LineCost(None, None, [r.code if r.code in ("unconvertible_unit", "needs_cost") else "needs_cost"], r.reason)

    def check(qty, price, stated, what) -> None:
        if qty is None or price is None or stated is None:
            return
        c = check_line_total(qty, price, stated)
        if not c.ok:
            flags.append("check_failed")
            checks.append(f"{what}: {qty:g} x {price:.2f} = {c.expected:.2f} but the line says {c.stated:.2f}")

    checks: list[str] = []

    if catch_weight:
        recv_text = (line.get("qty_received") or "").strip()
        if not recv_text:
            return LineCost(None, None, ["needs_cost"], "catch-weight line with no received weight")
        unit_name = unit_text if unit_text and not is_refusal(normalise_unit(unit_text)) else price_unit_text
        amount = amount_in(f"{recv_text} {unit_name or ''}".strip(), to_unit)
        if is_refusal(amount):
            return refuse(amount)
        recv_q = parse_number(recv_text.split()[0]) if recv_text.split() else None
        recv_unit = normalise_unit(unit_name) if unit_name else None
        if is_refusal(recv_unit) or recv_unit is None or is_refusal(recv_q):
            return LineCost(None, None, ["unconvertible_unit"], f"cannot read the received weight {recv_text!r} {unit_name or ''}")
        if ext is not None:
            cost = unit_cost_catch_weight(ext, float(recv_q), recv_unit, to_unit)
        elif unit_price is not None and price_unit_text:
            pu = normalise_unit(price_unit_text)
            cost = pu if is_refusal(pu) else unit_cost_from_unit_price(unit_price, pu, to_unit)
        else:
            return LineCost(None, None, ["needs_cost"], "catch-weight line with no extended or unit price")
        if is_refusal(cost):
            return refuse(cost)
        if unit_price is not None and ext is not None and price_unit_text:
            pu = normalise_unit(price_unit_text)
            if not is_refusal(pu) and dimension(pu) == dimension(recv_unit):
                check(convert(float(recv_q), recv_unit, pu), unit_price, ext, "received weight")
        return LineCost(cost, amount, flags, "; ".join(checks) or "catch weight: billed on received weight")

    if unit_price is None:
        return LineCost(None, None, ["needs_cost"], "no unit price on the line")

    price_per_case = pack_text and (price_unit_text is None or _case_word(price_unit_text)) and (unit_text is None or _case_word(unit_text) or price_unit_text is not None)
    if pack_text and price_per_case and (price_unit_text is not None or _case_word(unit_text) or unit_text is None):
        pack = parse_pack(pack_text)
        if is_refusal(pack):
            return refuse(pack)
        cost = unit_cost_from_case(unit_price, pack, to_unit)
        if is_refusal(cost):
            return refuse(cost)
        per_case = pack_quantity(pack, to_unit)
        qty = parse_number(line["qty_ordered"]) if line.get("qty_ordered") else None
        cases = None if qty is None or is_refusal(qty) else float(qty)
        check(cases, unit_price, ext, "cases")
        return LineCost(cost, None if cases is None else cases * per_case, flags, "; ".join(checks) or f"case price over {pack_text}")

    # a price per unit (lb, qt, each ...), with or without a pack
    unit_name = price_unit_text or unit_text
    if not unit_name:
        return LineCost(None, None, ["needs_cost"], "no unit on the line")
    canon = normalise_unit(unit_name)
    if is_refusal(canon):
        return refuse(canon)
    cost = unit_cost_from_unit_price(unit_price, canon, to_unit)
    if is_refusal(cost):
        return refuse(cost)
    qty_text = line.get("qty_ordered") or line.get("qty_received")
    qty = parse_number(qty_text) if qty_text else None
    qn = None if qty is None or is_refusal(qty) else float(qty)
    check(qn, unit_price, ext, "quantity")
    per_unit = convert(1, canon, to_unit)
    return LineCost(cost, None if qn is None else qn * per_unit, flags, "; ".join(checks) or "unit price")


# ------------------------------------------------------------------ the model call with checks and one retry
def _slug(text: str, taken: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:30] or "new_ingredient"
    slug, n = base, 2
    while slug in taken:
        slug, n = f"{base}_{n}", n + 1
    return slug


def semantic_failures(kind: str, data: dict, doc_lines: list[str], catalogue: Catalogue) -> list[str]:
    """Failures a retry could fix: a quote not found in the document, a line total that disagrees."""
    out = []
    for key in ("lines", "other_lines"):
        for ln in data.get(key, []):
            if locate(ln["source_quote"], doc_lines) is None:
                out.append(f"line_no {ln['line_no']}: source_quote was not found in the document; copy it verbatim")
    if kind == "invoice":
        for ln in data["lines"]:
            mid = ln["matched_ingredient_id"]
            unit = catalogue.ingredients.get(mid, {}).get("unit")
            if unit:
                lc = compute_line_cost(ln, unit)
                if "check_failed" in lc.flags:
                    out.append(f"line_no {ln['line_no']}: {lc.reason}; re-read the quantity and prices on that line")
    return out


def call_model(kind: str, text: str, client, catalogue: Catalogue, doc_lines: list[str]) -> tuple[dict, int, list[str]]:
    """One call, then at most one retry with the failures fed back. Returns (data, retries, remaining failures)."""
    mc.check_document_size(text)
    system = mc.load_prompt(kind)
    schema = mc.load_schema(kind)
    context = catalogue.ingredient_context() if kind == "invoice" else catalogue.recipe_context()
    user = mc.build_user_message(text, context)
    data = client.complete_json(system, user, schema)
    mc.validate_output(kind, data)
    failures = semantic_failures(kind, data, doc_lines, catalogue)
    retries = 0
    if failures:
        feedback = "Your previous answer had these problems. Fix them and return the full JSON again:\n- " + "\n- ".join(failures)
        retry = client.complete_json(system, user + "\n\n" + feedback, schema)
        mc.validate_output(kind, retry)
        retries = 1
        again = semantic_failures(kind, retry, doc_lines, catalogue)
        if len(again) <= len(failures):
            data, failures = retry, again
    return data, retries, failures


# ------------------------------------------------------------------ invoices
def parse_invoice(text: str, client, catalogue: Catalogue, source_name: str = "invoice.txt") -> ParseResult:
    doc_lines = text.splitlines()
    sha = source_hash(text)
    data, retries, remaining = call_model("invoice", text, client, catalogue, doc_lines)
    rows: list[StagedRow] = []

    week = ""
    date_flag: list[str] = []
    if data["invoice_date"] and not is_refusal(d := parse_date(data["invoice_date"])):
        week = week_monday(d).isoformat()
    else:
        date_flag = ["missing_date"]

    taken = set(catalogue.ingredients)
    costed: list[tuple[StagedRow, float | None]] = []  # cost rows with their weighting quantity
    for ln in data["lines"]:
        src = locate(ln["source_quote"], doc_lines)
        flags = list(date_flag)
        reasons = []
        if src is None:
            flags.append("check_failed")
            reasons.append("source quote not found in the document")
            src = ln["line_no"] if 1 <= ln["line_no"] <= len(doc_lines) else None
        mid = ln["matched_ingredient_id"]
        new_unit = None
        if mid == "NEW":
            flags.append("new_ingredient")
            to_unit, ingredient_id = None, ""
        elif mid not in catalogue.ingredients:
            flags += ["ambiguous_name", "needs_cost"]
            reasons.append(f"the model returned {mid!r}, which is not in the catalogue")
            rows.append(StagedRow.create(make_row_id(sha, src or 0, "cost"), "cost", flags=tuple(flags), ingredient_id="",
                                         effective_week=week, reason="; ".join(reasons), source_line=src, source_quote=ln["source_quote"]))
            continue
        else:
            to_unit, ingredient_id = catalogue.ingredients[mid]["unit"], mid
            if ln["status"] == "ambiguous":
                flags.append("ambiguous_name")
                reasons.append("the model found more than one plausible ingredient")
            elif ln["status"] == "missing":
                flags += ["ambiguous_name", "needs_cost"]
                reasons.append("the model could not tell which ingredient or what the line says")

        if mid == "NEW":
            new_unit = _proposed_unit(ln)
            slug = _slug(ln["description"], taken)
            taken.add(slug)
            ingredient_id, to_unit = slug, new_unit
            rows.append(StagedRow.create(make_row_id(sha, src or 0, "ingredient"), "ingredient", flags=("new_ingredient",),
                                         ingredient_id=slug, name=ln["description"].title(), unit=new_unit,
                                         reason="a new ingredient proposed from the invoice description",
                                         source_line=src, source_quote=ln["source_quote"]))

        if "needs_cost" in flags and mid != "NEW":
            cost = LineCost(None, None, [], "")
        else:
            cost = compute_line_cost(ln, to_unit)
        flags += cost.flags
        reasons.append(cost.reason)
        key = (ingredient_id, week)
        row = StagedRow.create(make_row_id(sha, src or 0, "cost"), "cost", flags=tuple(flags), ingredient_id=ingredient_id,
                               effective_week=week, unit_cost=cost.unit_cost, unit=to_unit or "",
                               reason="; ".join(r for r in reasons if r), source_line=src, source_quote=ln["source_quote"])
        costed.append((row, cost.quantity))
        rows.append(row)

    rows = _merge_duplicate_costs(rows, costed, week)
    for row in rows:
        if row.kind == "cost" and row.status != "skipped" and (row.ingredient_id, row.effective_week) in catalogue.existing_costs:
            if "update" not in row.flags:
                row.flags += ("update",)
                row.status = "flagged"
                row.reason += "; this would replace the existing cost row for that ingredient and week"

    for other in data["other_lines"]:
        src = locate(other["source_quote"], doc_lines) or (other["line_no"] if 1 <= other["line_no"] <= len(doc_lines) else None)
        rows.append(StagedRow.create(make_row_id(sha, src or 0, "cost", "other"), "cost", skipped=True, reason=other["category"],
                                     source_line=src, source_quote=other["source_quote"]))
    meta = RunMeta(kind="invoice", mode=client.mode, model=client.model, prompt_version=mc.PROMPT_VERSIONS["invoice"],
                   schema_version=mc.SCHEMA_VERSIONS["invoice"], source_file=source_name, source_sha256=sha,
                   calls=client.calls, retries=retries)
    return ParseResult(rows, meta, remaining)


def _proposed_unit(line: dict) -> str:
    """A new ingredient's unit must be one of the existing seven; take the pack or price unit when it is one,
    else the default for its dimension (weight lb, volume gal, count each)."""
    seven = ("lb", "qt", "gal", "oz", "each", "doz", "head")
    pack = parse_pack(line.get("pack_text") or "") if line.get("pack_text") else None
    candidates = []
    if pack is not None and not is_refusal(pack) and not pack.unit.startswith("#"):
        candidates.append(pack.unit)
    for t in (line.get("price_unit_text"), line.get("unit_text")):
        if t and not is_refusal(normalise_unit(t)):
            candidates.append(normalise_unit(t))
    for c in candidates:
        if c in seven:
            return c
        if c in UNITS:
            return DEFAULT_UNIT_BY_DIMENSION[dimension(c)]
    return "lb"


def _merge_duplicate_costs(rows: list[StagedRow], costed: list[tuple[StagedRow, float | None]], week: str) -> list[StagedRow]:
    """One staged row per ingredient and week: the quantity-weighted average, flagged `conflict`.
    Without quantities the first row is kept and flagged, and the others are listed in its reason."""
    groups: dict[tuple[str, str], list[tuple[StagedRow, float | None]]] = {}
    for row, qty in costed:
        groups.setdefault((row.ingredient_id, row.effective_week), []).append((row, qty))
    drop: set[str] = set()
    for (ing, wk), members in groups.items():
        if len(members) < 2 or not ing:
            continue
        first = members[0][0]
        valued = [(r, q) for r, q in members if r.unit_cost is not None]
        if valued and all(q for _, q in valued):
            total = sum(q for _, q in valued)
            first.unit_cost = sum(r.unit_cost * q for r, q in valued) / total
        lines = ", ".join(str(r.source_line) for r, _ in members)
        first.flags = tuple(dict.fromkeys(first.flags + ("conflict",)))
        first.status = "flagged"
        first.reason += f"; the same ingredient appears on lines {lines} for one week: quantity-weighted average proposed"
        for r, _ in members[1:]:
            drop.add(r.row_id)
    return [r for r in rows if r.row_id not in drop]


# ------------------------------------------------------------------ recipes
def parse_recipe(text: str, client, catalogue: Catalogue, source_name: str = "recipe.txt") -> ParseResult:
    doc_lines = text.splitlines()
    sha = source_hash(text)
    data, retries, remaining = call_model("recipe", text, client, catalogue, doc_lines)
    rows: list[StagedRow] = []
    dish = data["matched_item_id"] if data["matched_item_id"] in catalogue.items else None
    servings = None
    if data["servings"]:
        s = parse_number(data["servings"].split()[0]) if data["servings"].split() else None
        servings = None if s is None or is_refusal(s) or s <= 0 else s
    taken = set(catalogue.ingredients)

    for ln in data["lines"]:
        src = locate(ln["source_quote"], doc_lines)
        flags: list[str] = []
        reasons: list[str] = []
        if src is None:
            flags.append("check_failed")
            reasons.append("source quote not found in the document")
            src = ln["line_no"] if 1 <= ln["line_no"] <= len(doc_lines) else None
        if dish is None:
            flags.append("ambiguous_name")
            reasons.append("the dish is not an item on the menu: the parser never invents menu items")
            rows.append(StagedRow.create(make_row_id(sha, src or 0, "recipe_line"), "recipe_line", flags=tuple(flags),
                                         reason="; ".join(reasons), source_line=src, source_quote=ln["source_quote"]))
            continue
        # unquantified lines ("to taste") are skipped with a note
        if not _quantified(ln["quantity_text"], ln["unit_text"]):
            rows.append(StagedRow.create(make_row_id(sha, src or 0, "recipe_line"), "recipe_line", skipped=True,
                                         reason=f"unquantified: {ln['quantity_text'] or ln['ingredient_text']!r}",
                                         source_line=src, source_quote=ln["source_quote"]))
            continue
        mid = ln["matched_ingredient_id"]
        to_unit, ingredient_id = None, ""
        if mid == "NEW":
            slug = _slug(ln["ingredient_text"], taken)
            taken.add(slug)
            unit_guess = _recipe_unit(ln)
            rows.append(StagedRow.create(make_row_id(sha, src or 0, "ingredient"), "ingredient", flags=("new_ingredient",),
                                         ingredient_id=slug, name=ln["ingredient_text"].title(), unit=unit_guess,
                                         reason="a new ingredient proposed from the recipe line", source_line=src, source_quote=ln["source_quote"]))
            ingredient_id, to_unit = slug, unit_guess
            flags.append("new_ingredient")
        elif mid in catalogue.ingredients:
            ingredient_id, to_unit = mid, catalogue.ingredients[mid]["unit"]
            if ln["status"] == "ambiguous":
                flags.append("ambiguous_name")
                reasons.append("the model found more than one plausible ingredient")
            elif ln["status"] == "missing":
                flags += ["ambiguous_name", "needs_cost"]
        else:
            flags += ["ambiguous_name", "needs_cost"]
            reasons.append(f"the model returned {mid!r}, which is not in the catalogue")

        qty_text = " ".join(x for x in (ln["quantity_text"], ln["unit_text"]) if x).strip()
        note = ln["note"] or ""
        if YIELD_WORDS.search(note) or YIELD_WORDS.search(ln["source_quote"]):
            flags.append("no_yield_applied")
        total, flag, why = _recipe_total(qty_text, ln["quantity_text"], ln["unit_text"], to_unit)
        flags += flag
        reasons.append(why)
        qty_per_serving = None
        if servings is None:
            flags.append("missing_servings")
            reasons.append("the recipe gives no serving count")
        elif total is not None and "needs_cost" not in flags:
            qty_per_serving = total / float(servings)
        if total is None and not any(f in flags for f in ("unconvertible_unit", "needs_cost")):
            flags.append("needs_cost")
        if dish in catalogue.existing_recipes:
            flags.append("update")
            reasons.append("this recipe would replace the existing recipe rows for the dish")
        rows.append(StagedRow.create(make_row_id(sha, src or 0, "recipe_line"), "recipe_line", flags=tuple(flags), item_id=dish,
                                     ingredient_id=ingredient_id, qty_per_serving=qty_per_serving,
                                     reason="; ".join(r for r in reasons if r), source_line=src, source_quote=ln["source_quote"]))
    meta = RunMeta(kind="recipe", mode=client.mode, model=client.model, prompt_version=mc.PROMPT_VERSIONS["recipe"],
                   schema_version=mc.SCHEMA_VERSIONS["recipe"], source_file=source_name, source_sha256=sha,
                   calls=client.calls, retries=retries)
    return ParseResult(rows, meta, remaining)


def _is_range(text: str) -> bool:
    return bool(re.search(r"\d\s*(?:-|to)\s*\d", text))


def _quantified(quantity_text: str | None, unit_text: str | None) -> bool:
    """True if the line gives an amount we can read: a number, a compound amount or a range."""
    if not quantity_text:
        return False
    full = f"{quantity_text} {unit_text or ''}".strip()
    return not is_refusal(parse_amount(full)) or _is_range(full) or not is_refusal(parse_quantity(quantity_text))


def _recipe_unit(line: dict) -> str:
    seven = ("lb", "qt", "gal", "oz", "each", "doz", "head")
    for t in (line.get("unit_text"), line.get("quantity_text")):
        if t:
            parts = re.findall(r"[A-Za-z#.]+", t)
            for p in reversed(parts):
                u = normalise_unit(p)
                if not is_refusal(u):
                    return u if u in seven else DEFAULT_UNIT_BY_DIMENSION[dimension(u)]
    return "lb"


def _recipe_total(qty_text: str, quantity_text: str | None, unit_text: str | None, to_unit: str | None):
    """(total in the ingredient's unit | None, flags, reason). A range stages its midpoint with a flag."""
    if to_unit is None:
        return None, ["needs_cost"], "the ingredient is unknown, so the quantity cannot be converted"
    total = amount_in(qty_text, to_unit)
    if not is_refusal(total):
        return total, [], f"{qty_text}"
    m = re.match(r"^\s*(?P<lo>[\d\s/.¼-¾⅐-⅞]+?)\s*(?:-|to)\s*(?P<hi>[\d\s/.¼-¾⅐-⅞]+?)\s*(?P<u>[A-Za-z#. ]*)$", qty_text)
    if m and (unit_name := (m.group("u").strip() or unit_text)):
        lo, hi, unit = parse_number(m.group("lo")), parse_number(m.group("hi")), normalise_unit(unit_name)
        if not (is_refusal(lo) or is_refusal(hi) or is_refusal(unit)):
            mid = convert((lo + hi) / 2, unit, to_unit)
            if not is_refusal(mid):
                return mid, ["range_midpoint"], f"range {qty_text!r} staged as its midpoint"
            return None, [mid.code], mid.reason
    return None, [total.code if total.code in ("unconvertible_unit",) else "needs_cost"], total.reason


# ------------------------------------------------------------------ entry
def parse_document(path: Path, kind: str, client, catalogue: Catalogue) -> ParseResult:
    path = Path(path)
    text = path.read_text()
    fn = parse_invoice if kind == "invoice" else parse_recipe
    return fn(text, client, catalogue, source_name=path.name)
