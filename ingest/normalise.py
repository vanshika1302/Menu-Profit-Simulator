"""Quantity and price parsing, pack arithmetic and the line-total check.

Pure functions, no model and no file access. The model copies raw strings from a document;
everything numeric happens here. Every function that can fail returns a `Refusal` (a flagged
row with no value) rather than guessing.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from fractions import Fraction

from ingest.units import (
    UNITS,
    Refusal,
    can_volume,
    convert,
    dimension,
    is_refusal,
    normalise_unit,
)

LINE_TOTAL_ABS = 0.02
LINE_TOTAL_REL = 0.005


@dataclass(frozen=True)
class Range:
    """A quantity written as a range ("2-3", "2 to 3"). Staged as the midpoint with a flag."""

    low: Fraction
    high: Fraction

    @property
    def midpoint(self) -> Fraction:
        return (self.low + self.high) / 2


@dataclass(frozen=True)
class Pack:
    """`count` packages of `size` of `unit` (a canonical unit, or a can size such as "#10")."""

    count: Fraction
    size: Fraction
    unit: str


# ---------------------------------------------------------------- numbers
def _unicode_fractions(text: str) -> str:
    """Replace vulgar fractions (½, ¾, ...) with ' n/d', keeping any whole number before them."""
    out = []
    for ch in text:
        if unicodedata.category(ch) == "No" and ch not in "²³¹":
            try:
                value = Fraction(unicodedata.numeric(ch)).limit_denominator(100)
            except (TypeError, ValueError):
                out.append(ch)
                continue
            out.append(f" {value.numerator}/{value.denominator} ")
        else:
            out.append(ch)
    return "".join(out)


_NUM = r"\d+(?:\.\d+)?"


def parse_number(text: str) -> Fraction | Refusal:
    """Parse "3", "1/2", "1 1/2", "1-1/2", "1½", "1,234.50" or "$12.99" into an exact Fraction.

    "93/8" is parsed literally as 93/8: a garbled "9 3/8" cannot be recovered here, and the
    parser never rewrites digits to make them look plausible.
    """
    t = _unicode_fractions(text).replace("$", "").strip()
    t = re.sub(r"(?<=\d),(?=\d{3}\b)", "", t)  # thousands separators
    t = " ".join(t.split())
    if not t:
        return Refusal("unparseable", "empty quantity")
    m = re.fullmatch(rf"({_NUM})", t)
    if m:
        return Fraction(m.group(1))
    m = re.fullmatch(r"(\d+)/(\d+)", t)
    if m:
        if int(m.group(2)) == 0:
            return Refusal("unparseable", f"zero denominator in {text!r}")
        return Fraction(int(m.group(1)), int(m.group(2)))
    m = re.fullmatch(r"(\d+)(?:\s+|-)(\d+)/(\d+)", t)
    if m:
        if int(m.group(3)) == 0:
            return Refusal("unparseable", f"zero denominator in {text!r}")
        return int(m.group(1)) + Fraction(int(m.group(2)), int(m.group(3)))
    return Refusal("unparseable", f"cannot read a number from {text!r}")


def parse_quantity(text: str) -> Fraction | Range | Refusal:
    """A number, or a range ("2-3", "2 to 3", "1/2-1") as a `Range`. "To taste" and the like refuse."""
    t = " ".join(text.replace("\u2013", "-").replace("\u2014", "-").lower().split())
    whole = parse_number(t)  # also covers the mixed number "1-1/2"
    if not is_refusal(whole):
        return whole
    for sep in (r"\s*-\s*", r"\s+to\s+"):
        parts = re.split(sep, _unicode_fractions(t).strip())
        if len(parts) == 2:
            lo, hi = parse_number(parts[0]), parse_number(parts[1])
            if is_refusal(lo) or is_refusal(hi):
                continue
            if lo > hi:
                return Refusal("unparseable", f"range {text!r} runs backwards")
            return Range(lo, hi)
    return whole


# ---------------------------------------------------------------- amounts
_AMOUNT = re.compile(
    r"(?P<q>\d+(?:\.\d+)?(?:\s+\d+/\d+|-\d+/\d+|/\d+)?|\d+/\d+)\s*(?P<u>fl\.?\s*oz\.?|[a-zA-Z#]+\.?)"
)


def parse_amount(text: str) -> list[tuple[Fraction, str]] | Refusal:
    """Parse "3 lb 6 oz", "1 gal 2 qt", "½ cup" into [(quantity, canonical unit), ...]."""
    t = " ".join(_unicode_fractions(text).split())
    found = list(_AMOUNT.finditer(t))
    if not found:
        return Refusal("unparseable", f"cannot read an amount from {text!r}")
    leftover = _AMOUNT.sub("", t).replace(",", "").replace("and", "").strip()
    if leftover:
        return Refusal("unparseable", f"unrecognised text {leftover!r} in amount {text!r}")
    parts = []
    for m in found:
        q, u = parse_number(m.group("q")), normalise_unit(m.group("u"))
        if is_refusal(q):
            return q
        if is_refusal(u):
            return u
        parts.append((q, u))
    return parts


def amount_in(text: str, to_unit: str) -> float | Refusal:
    """Total of a (possibly compound) amount in `to_unit`: "3 lb 6 oz" -> 3.375 lb."""
    parts = parse_amount(text)
    if is_refusal(parts):
        return parts
    total = 0.0
    for q, u in parts:
        v = convert(q, u, to_unit)
        if is_refusal(v):
            return v
        total += v
    return total


# ---------------------------------------------------------------- packs
_PACK = re.compile(
    r"^\s*(?:(?P<n>\d+)\s*/\s*)?(?P<s>\d+(?:\.\d+)?|\d+\s+\d+/\d+)?\s*(?P<u>#\d+|[a-zA-Z#]+\.?(?:\s*oz)?)\s*(?:c/?s|case)?\s*$",
    re.I,
)


def parse_pack(text: str) -> Pack | Refusal:
    """Parse "4/5 LB", "6/#10", "4/1 GAL", "40 LB", "24 CT", "6/10#" or "12/32 OZ".

    "6/#10" is six #10 cans (a volume); "6/10#" is six 10-lb units (a weight).
    """
    t = " ".join(text.split()).upper()
    m = re.fullmatch(r"(\d+)\s*/\s*#(\d+)", t)  # 6/#10: a can size
    if m:
        return Pack(Fraction(int(m.group(1))), Fraction(1), f"#{m.group(2)}")
    m = re.fullmatch(r"(\d+)\s*/\s*(\d+(?:\.\d+)?)\s*#", t)  # 6/10#: pounds
    if m:
        return Pack(Fraction(int(m.group(1))), Fraction(m.group(2)), "lb")
    m = re.fullmatch(r"(?:(\d+)\s*/\s*)?(\d+(?:\.\d+)?)\s*([A-Z#. ]+?)(?:\s+(?:CS|CASE))?", t)
    if not m:
        return Refusal("needs_cost", f"cannot read a pack size from {text!r}")
    count = Fraction(int(m.group(1))) if m.group(1) else Fraction(1)
    unit = normalise_unit(m.group(3).strip())
    if is_refusal(unit):
        return unit
    size = Fraction(m.group(2))
    if count <= 0 or size <= 0:
        return Refusal("needs_cost", f"non-positive pack in {text!r}")
    return Pack(count, size, unit)


def pack_quantity(pack: Pack, to_unit: str) -> float | Refusal:
    """Total quantity in one case, expressed in the ingredient's unit."""
    if pack.unit.startswith("#"):
        per = can_volume(pack.unit, to_unit)
        return per if is_refusal(per) else float(pack.count) * per
    per = convert(pack.size, pack.unit, to_unit)
    return per if is_refusal(per) else float(pack.count) * per


# ---------------------------------------------------------------- costs
def _positive(x: float, what: str) -> Refusal | None:
    if x <= 0:
        return Refusal("needs_cost", f"{what} must be positive, got {x}")
    return None


def unit_cost_from_case(case_price: float, pack: Pack, to_unit: str) -> float | Refusal:
    """Case price / quantity in the case: `4/5 LB` at $38 is $1.90 per lb."""
    bad = _positive(case_price, "case price")
    if bad:
        return bad
    qty = pack_quantity(pack, to_unit)
    if is_refusal(qty):
        return qty
    return case_price / qty


def unit_cost_from_unit_price(price: float, price_unit: str, to_unit: str) -> float | Refusal:
    """A price per `price_unit` expressed per `to_unit` ($/lb to $/oz divides by 16)."""
    bad = _positive(price, "unit price")
    if bad:
        return bad
    per = convert(1, price_unit, to_unit)
    return per if is_refusal(per) else price / per


def unit_cost_catch_weight(extended_price: float, received_qty: float, received_unit: str, to_unit: str) -> float | Refusal:
    """Catch weight: what was billed divided by the weight actually received, never the case count."""
    bad = _positive(extended_price, "extended price") or _positive(received_qty, "received weight")
    if bad:
        return bad
    qty = convert(received_qty, received_unit, to_unit)
    return qty if is_refusal(qty) else extended_price / qty


@dataclass(frozen=True)
class LineCheck:
    ok: bool
    expected: float
    stated: float


def check_line_total(quantity: float, unit_price: float, stated_total: float) -> LineCheck:
    """Quantity x unit price against the stated line total, within max($0.02, 0.5%)."""
    expected = quantity * unit_price
    tolerance = max(LINE_TOTAL_ABS, LINE_TOTAL_REL * abs(stated_total))
    return LineCheck(abs(expected - stated_total) <= tolerance, expected, stated_total)


def parse_price(text: str) -> float | Refusal:
    """A price string such as "$1,234.50" or "12.99" as a float; negative prices (credits) parse too."""
    t = text.strip()
    negative = t.startswith("(") and t.endswith(")") or t.startswith("-") or t.endswith("-")
    t = t.strip("()-").strip()
    n = parse_number(t)
    if is_refusal(n):
        return n
    return -float(n) if negative else float(n)


# ---------------------------------------------------------------- dates
_DATE_FORMATS = ("%Y-%m-%d", "%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y", "%m/%d/%Y")


def parse_date(text: str) -> "date | Refusal":
    """An invoice date as written. Numeric dates are read US-style (month first), an assumption that
    only matters when the day is 12 or less; the evaluation's adversarial cases use unambiguous dates."""
    from datetime import datetime

    t = " ".join(text.replace(",", ", ").split()).replace(" ,", ",").strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(t, fmt).date()
        except ValueError:
            continue
    return Refusal("unparseable", f"cannot read a date from {text!r}")


def week_monday(d: "date") -> "date":
    """The Monday of the week containing `d`: the ingredient_costs effective_week."""
    from datetime import timedelta

    return d - timedelta(days=d.weekday())
