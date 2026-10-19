"""Unit tables and exact conversions for the invoice and recipe parser.

Conversions are exact within one dimension (weight, volume, count) and refused across
dimensions: there is no density table, so weight-to-volume and count-to-weight never
convert. A refusal is a value (`Refusal`), not an exception, so callers stage a flagged
row instead of guessing.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

# The ingredient's own unit is always one of these seven (see the target-mapping ticket).
INGREDIENT_UNITS = ("lb", "qt", "gal", "oz", "each", "doz", "head")


@dataclass(frozen=True)
class Refusal:
    """Why no value could be computed. `code` is a staging flag code."""

    code: str  # "unconvertible_unit" | "needs_cost" | "unparseable"
    reason: str


def is_refusal(x) -> bool:
    return isinstance(x, Refusal)


# canonical unit -> (dimension, amount in the dimension's base unit)
# bases: weight in oz, volume in US fl oz, count in each.
_G_PER_OZ = Fraction(28349523125, 1_000_000_000)  # exact definition of the avoirdupois ounce
_ML_PER_FL_OZ = Fraction(295735295625, 10_000_000_000)  # exact definition of the US fluid ounce
UNITS: dict[str, tuple[str, Fraction]] = {
    "oz": ("weight", Fraction(1)),
    "lb": ("weight", Fraction(16)),
    "g": ("weight", 1 / _G_PER_OZ),
    "kg": ("weight", 1000 / _G_PER_OZ),
    "fl oz": ("volume", Fraction(1)),
    "cup": ("volume", Fraction(8)),
    "pint": ("volume", Fraction(16)),
    "qt": ("volume", Fraction(32)),
    "gal": ("volume", Fraction(128)),
    "ml": ("volume", 1 / _ML_PER_FL_OZ),
    "l": ("volume", 1000 / _ML_PER_FL_OZ),
    "each": ("count", Fraction(1)),
    "head": ("count", Fraction(1)),
    "doz": ("count", Fraction(12)),
}

# Spellings seen on invoices and recipes -> canonical unit. "oz" alone means weight; volume
# ounces must say "fl oz". "bunch", "cs" and "case" are deliberately absent: a bunch has no
# fixed count and a case is a package, not a unit.
ALIASES: dict[str, str] = {
    **{k: "lb" for k in ("lb", "lbs", "pound", "pounds", "#", "lb.")},
    **{k: "oz" for k in ("oz", "ounce", "ounces", "oz.")},
    **{k: "g" for k in ("g", "gram", "grams", "gm")},
    **{k: "kg" for k in ("kg", "kilo", "kilos", "kilogram", "kilograms")},
    **{k: "fl oz" for k in ("fl oz", "floz", "fl. oz", "fl. oz.", "fluid ounce", "fluid ounces")},
    **{k: "cup" for k in ("cup", "cups", "c")},
    **{k: "pint" for k in ("pint", "pints", "pt")},
    **{k: "qt" for k in ("qt", "qts", "quart", "quarts")},
    **{k: "gal" for k in ("gal", "gals", "gallon", "gallons")},
    **{k: "ml" for k in ("ml", "milliliter", "milliliters", "millilitre", "millilitres")},
    **{k: "l" for k in ("l", "lt", "ltr", "liter", "liters", "litre", "litres")},
    **{k: "each" for k in ("each", "ea", "ct", "count", "pc", "pcs", "piece", "pieces", "unit", "units")},
    **{k: "doz" for k in ("doz", "dz", "dozen")},
    **{k: "head" for k in ("head", "heads", "hd")},
}

# Can sizes are approximate volumes in fl oz and apply only when the ingredient's own unit
# is a volume. Only sizes with a source are listed; any other can size is refused. The #10
# figure is the USDA's approximate volume (the formats research ticket cites about 108 oz).
CAN_SIZES_FL_OZ: dict[str, Fraction] = {"#10": Fraction(108)}


def normalise_unit(text: str) -> str | Refusal:
    """Canonical unit for an invoice or recipe spelling, or a refusal if unknown."""
    key = " ".join(text.lower().split())
    for candidate in (key, key.rstrip("."), key.replace(".", ""), key.replace(".", "").replace(" ", "")):
        if candidate in ALIASES:
            return ALIASES[candidate]
    return Refusal("unconvertible_unit", f"unknown unit {text!r}")


def dimension(unit: str) -> str:
    return UNITS[unit][0]


def convert(qty: Fraction | float, from_unit: str, to_unit: str) -> float | Refusal:
    """Convert `qty` of canonical `from_unit` into canonical `to_unit`, or refuse."""
    if from_unit not in UNITS or to_unit not in UNITS:
        return Refusal("unconvertible_unit", f"unknown unit {from_unit!r} or {to_unit!r}")
    (d_from, f_from), (d_to, f_to) = UNITS[from_unit], UNITS[to_unit]
    if d_from != d_to:
        return Refusal("unconvertible_unit", f"cannot convert {d_from} ({from_unit}) to {d_to} ({to_unit}): no density table")
    return float(Fraction(qty) * f_from / f_to)


def can_volume(can_size: str, to_unit: str) -> float | Refusal:
    """Volume of one can of a known size in `to_unit`, only if `to_unit` is a volume."""
    size = CAN_SIZES_FL_OZ.get(can_size)
    if size is None:
        return Refusal("unconvertible_unit", f"unknown can size {can_size!r}")
    if to_unit not in UNITS or dimension(to_unit) != "volume":
        return Refusal("unconvertible_unit", f"a {can_size} can has a volume, but the ingredient's unit {to_unit!r} is not a volume")
    return convert(size, "fl oz", to_unit)
