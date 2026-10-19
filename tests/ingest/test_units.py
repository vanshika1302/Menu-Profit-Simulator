from fractions import Fraction

import pytest

from ingest.units import Refusal, can_volume, convert, is_refusal, normalise_unit


def test_weight_conversions_are_exact():
    assert convert(1, "lb", "oz") == 16
    assert convert(32, "oz", "lb") == 2
    assert convert(1, "kg", "lb") == pytest.approx(2.2046226218, rel=1e-9)
    assert convert(454, "g", "lb") == pytest.approx(1.0009, rel=1e-3)


def test_volume_conversions_are_exact():
    assert convert(1, "gal", "qt") == 4
    assert convert(2, "pint", "qt") == 1
    assert convert(8, "fl oz", "cup") == 1
    assert convert(1, "l", "qt") == pytest.approx(1.0566882094, rel=1e-9)
    assert convert(1, "gal", "fl oz") == 128


def test_count_conversions():
    assert convert(2, "doz", "each") == 24
    assert convert(24, "each", "doz") == 2
    assert convert(3, "head", "each") == 3


def test_cross_dimension_is_refused_not_guessed():
    for a, b in (("lb", "qt"), ("qt", "lb"), ("each", "lb"), ("doz", "oz"), ("cup", "each")):
        r = convert(1, a, b)
        assert is_refusal(r) and r.code == "unconvertible_unit"
        assert "density" in r.reason or "unknown" in r.reason


def test_oz_means_weight_and_fl_oz_means_volume():
    assert normalise_unit("oz") == "oz" and normalise_unit("FL OZ") == "fl oz"
    assert is_refusal(convert(1, "oz", "fl oz"))


@pytest.mark.parametrize(
    "text,canonical",
    [("LBS", "lb"), ("lb.", "lb"), ("#", "lb"), ("Gallon", "gal"), ("QTS", "qt"), ("CT", "each"), ("ea", "each"),
     ("dozen", "doz"), ("fl. oz.", "fl oz"), ("Ltr", "l"), ("HD", "head"), ("c", "cup")],
)
def test_unit_spellings(text, canonical):
    assert normalise_unit(text) == canonical


@pytest.mark.parametrize("text", ["bunch", "cs", "case", "pallet", "", "flarb"])
def test_unknown_units_are_refused(text):
    r = normalise_unit(text)
    assert isinstance(r, Refusal) and r.code == "unconvertible_unit"


def test_can_volume_only_for_volume_ingredients():
    assert can_volume("#10", "fl oz") == 108
    assert can_volume("#10", "qt") == pytest.approx(3.375)
    assert can_volume("#10", "gal") == pytest.approx(108 / 128)
    for unit in ("lb", "each", "doz", "oz"):
        r = can_volume("#10", unit)
        assert is_refusal(r) and "not a volume" in r.reason


def test_unknown_can_size_is_refused():
    r = can_volume("#303", "qt")
    assert is_refusal(r) and "unknown can size" in r.reason
