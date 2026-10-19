"""A rule-based extractor: the "what a regex gets" baseline for the scorecard.

It reads the evaluation documents with a few regular expressions and matches names to the catalogue by
shared words. It never sees the truth. It plugs in as the StubClient's extractor, so it fills the same
schema a model does and goes through the same parse pipeline, checks and scoring. It is deliberately
simple: it handles the three supplier layouts and plain recipe lines, and fails where a rule cannot
(abbreviated names, ambiguous names, prose notes), which is what the model is measured against.
"""
from __future__ import annotations

import re

UNICODE_FRAC = "¼½¾⅐⅑⅒⅓⅔⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞"
CASE = {"CS", "CASE"}
OTHER = [("fuel", "fee"), ("surcharge", "fee"), ("credit", "credit"), ("prompt pay", "discount"), ("discount", "discount"),
         ("deposit", "deposit"), ("allowance", "discount"), ("freight", "fee")]
STOP = {"of", "and", "the", "fresh", "dry"}


def split_message(user: str) -> tuple[str, str]:
    m = re.search(r"<document>\n(.*)\n</document>", user, re.S)
    text = m.group(1) if m else user
    return user[: m.start()] if m else "", text


def read_catalogue(context: str) -> dict[str, str]:
    """id -> name from lines `id | name | unit` (ingredients) in the context."""
    out = {}
    for line in context.splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) == 3 and re.fullmatch(r"[a-z0-9_]+", parts[0]):
            out[parts[0]] = parts[1]
    return out


def tokens(text: str) -> set[str]:
    return {t[:-1] if t.endswith("s") and len(t) > 3 else t for t in re.findall(r"[a-z0-9]+", text.lower())} - STOP


def match_name(desc: str, catalogue: dict[str, str]) -> tuple[str, str]:
    """(ingredient_id or 'NEW', status). A catalogue name matches when all its words appear in the text."""
    d = tokens(desc)
    hits = [(i, tokens(n)) for i, n in catalogue.items() if tokens(n) and tokens(n) <= d]
    if not hits:
        return "NEW", "ok"
    best = max(len(t) for _, t in hits)
    top = [i for i, t in hits if len(t) == best]
    return top[0], "ok" if len(top) == 1 else "ambiguous"


# ------------------------------------------------------------------ invoices
STYLE1 = re.compile(r"^(?P<n>\d+)\.\s+(?P<desc>.+?)(?: - (?P<pack>[^@=]+?))? - qty (?P<qty>[\d.,]+) (?P<unit>\S+) @ \$(?P<price>[\d,.]+) = \$(?P<ext>[\d,.]*)$")


def _line(no, quote, desc, pack, qty, unit, price, ext, catalogue):
    pack = (pack or "").strip() or None
    unit = (unit or "").strip().upper() or None
    iid, status = match_name(desc, catalogue)
    out = {"line_no": no, "description": desc.strip(), "pack_text": pack, "qty_ordered": qty or None, "qty_received": None,
           "unit_text": unit, "unit_price": price or None, "price_unit_text": unit, "extended_price": ext or None,
           "matched_ingredient_id": iid, "status": status, "source_quote": quote}
    if pack and pack.upper() == "CW":
        out.update(qty_ordered=None, qty_received=qty or None)
    elif unit in CASE:
        out["price_unit_text"] = None
    return out


def parse_invoice_text(text: str, catalogue: dict[str, str]) -> dict:
    lines = text.splitlines()
    out = {"supplier": lines[0].strip().title() if lines else None, "invoice_date": None, "lines": [], "other_lines": []}
    for no, raw in enumerate(lines, 1):
        s = raw.strip()
        if not s:
            continue
        m = re.match(r"Date:\s*(.+)$", s)
        if m:
            out["invoice_date"] = m.group(1).strip()
            continue
        low = s.lower()
        if low.startswith(("total", "invoice", "ship to", "ordered ")) or set(s) <= set("|-"):
            continue
        cat = next((c for key, c in OTHER if key in low and not s.startswith("|")), None)
        if cat:
            amt = re.findall(r"[\d,]+\.\d\d", s)
            out["other_lines"].append({"line_no": no, "category": cat, "description": s, "amount": amt[-1] if amt else None, "source_quote": s})
            continue
        m = STYLE1.match(s)
        if m:
            out["lines"].append(_line(no, s, m["desc"], m["pack"], m["qty"], m["unit"], m["price"], m["ext"], catalogue))
            continue
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if len(cells) == 6 and cells[0] != "DESCRIPTION":
                out["lines"].append(_line(no, s, cells[0], cells[1], cells[2], cells[3], cells[4], cells[5], catalogue))
            continue
        parts = re.split(r"\s{2,}", s)
        if len(parts) in (4, 5) and re.fullmatch(r"[\d,]+\.\d\d", parts[-1]):
            qty_unit = parts[-3].split()
            if len(qty_unit) == 2 and re.fullmatch(r"[\d.]+", qty_unit[0]):
                pack = parts[1] if len(parts) == 5 else None
                out["lines"].append(_line(no, s, parts[0], pack, qty_unit[0], qty_unit[1], parts[-2], parts[-1], catalogue))
    return out


# ------------------------------------------------------------------ recipes
NUM = rf"(?:\d+(?:\.\d+)?(?:\s+\d+/\d+)?[{UNICODE_FRAC}]?|\d+/\d+|[{UNICODE_FRAC}])"
RANGE = rf"{NUM}\s*-\s*{NUM}"
UNIT = r"(?:lbs?|oz|qt|gal|cups?|ea|doz|hd|ct|fl oz|g|kg|ml)"
PAIR = re.compile(rf"\s*(?P<q>{RANGE}|{NUM})\s*(?P<u>{UNIT})\b", re.I)


def parse_recipe_text(text: str, catalogue: dict[str, str], items: dict[str, str]) -> dict:
    lines = text.splitlines()
    dish = lines[0].strip() if lines else ""
    item_id = next((i for i, n in items.items() if n.lower() == dish.lower()), None)
    servings = None
    out_lines = []
    for no, raw in enumerate(lines, 1):
        s = raw.strip()
        m = re.match(r"Serves\s+(\d+)", s, re.I)
        if m:
            servings = m.group(1)
            continue
        if not s.startswith("-"):
            continue
        body = s[1:].strip()
        pairs, rest = [], body
        while True:
            m = PAIR.match(rest)
            if not m:
                break
            pairs.append((m["q"].strip(), m["u"].strip()))
            rest = rest[m.end():]
        note = None
        nm = re.search(r"\(([^)]*)\)\s*$", rest)
        if nm:
            note, rest = nm.group(1), rest[: nm.start()]
        name = re.sub(r",?\s*to taste$", "", rest.strip(" ,"), flags=re.I)
        if not pairs:
            q, u = None, None
        elif len(pairs) == 1:
            q, u = pairs[0]
        else:
            q, u = " ".join(f"{a} {b}" for a, b in pairs), None
        iid, status = match_name(name, catalogue)
        out_lines.append({"line_no": no, "quantity_text": q, "unit_text": u, "ingredient_text": name, "matched_ingredient_id": iid,
                          "note": note, "status": status, "source_quote": s})
    return {"dish_name": dish or None, "matched_item_id": item_id, "servings": servings, "lines": out_lines}


def rule_based_extractor(system: str, user: str, schema: dict) -> dict:
    """The StubClient extractor: reads whichever document the user message carries."""
    context, text = split_message(user)
    catalogue = read_catalogue(context)
    if "supplier" in schema["properties"]:
        return parse_invoice_text(text, catalogue)
    items = {}
    for line in context.splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) == 2 and re.fullmatch(r"[a-z0-9_]+", parts[0]):
            items[parts[0]] = parts[1]
    return parse_recipe_text(text, catalogue, items)
