from fractions import Fraction

import pytest

from ingest.normalise import (
    Pack,
    Range,
    amount_in,
    check_line_total,
    pack_quantity,
    parse_amount,
    parse_number,
    parse_pack,
    parse_price,
    parse_quantity,
    unit_cost_catch_weight,
    unit_cost_from_case,
    unit_cost_from_unit_price,
)
from ingest.units import is_refusal


# ---- numbers
@pytest.mark.parametrize(
    "text,value",
    [("3", 3), ("0.5", Fraction(1, 2)), ("1/2", Fraction(1, 2)), ("1 1/2", Fraction(3, 2)), ("1-1/2", Fraction(3, 2)),
     ("½", Fraction(1, 2)), ("1½", Fraction(3, 2)), ("2 ¾", Fraction(11, 4)), ("⅓", Fraction(1, 3)),
     ("1,234.50", Fraction("1234.50")), ("$12.99", Fraction("12.99"))],
)
def test_parse_number(text, value):
    assert parse_number(text) == value


def test_a_garbled_mixed_number_is_parsed_literally_not_repaired():
    # "9 3/8" exported as "93/8": the parser must not guess it back
    assert parse_number("93/8") == Fraction(93, 8)
    assert parse_number("93/8") != Fraction(75, 8)


@pytest.mark.parametrize("text", ["", "to taste", "a pinch", "1/0", "abc"])
def test_unreadable_numbers_refuse(text):
    assert is_refusal(parse_number(text))


def test_ranges_and_mixed_numbers_are_told_apart():
    assert parse_quantity("2-3") == Range(Fraction(2), Fraction(3))
    assert parse_quantity("2 to 3") == Range(Fraction(2), Fraction(3))
    assert parse_quantity("1/2-1") == Range(Fraction(1, 2), Fraction(1))
    assert parse_quantity("1-1/2") == Fraction(3, 2)  # a mixed number, not a range
    assert parse_quantity("2-3").midpoint == Fraction(5, 2)
    assert is_refusal(parse_quantity("3-2"))
    assert is_refusal(parse_quantity("to taste"))
    assert parse_quantity("4") == 4


# ---- compound amounts
def test_compound_amounts_sum_in_the_target_unit():
    assert amount_in("3 lb 6 oz", "lb") == pytest.approx(3.375)
    assert amount_in("3 lb 6 oz", "oz") == pytest.approx(54)
    assert amount_in("1 gal 2 qt", "qt") == pytest.approx(6)
    assert amount_in("1½ cups", "fl oz") == pytest.approx(12)
    assert amount_in("2 doz", "each") == 24


def test_amount_with_mixed_dimensions_refuses():
    assert is_refusal(amount_in("1 lb 2 cups", "lb"))
    assert is_refusal(amount_in("2 cups", "lb"))        # volume to weight: no density
    assert is_refusal(amount_in("a handful", "lb"))
    assert is_refusal(amount_in("2 bunches", "each"))   # a bunch has no fixed count


def test_parse_amount_returns_canonical_units():
    assert parse_amount("3 lb 6 oz") == [(Fraction(3), "lb"), (Fraction(6), "oz")]
    assert parse_amount("1/2 fl oz") == [(Fraction(1, 2), "fl oz")]


# ---- packs
@pytest.mark.parametrize(
    "text,pack",
    [("4/5 LB", Pack(Fraction(4), Fraction(5), "lb")), ("40 LB", Pack(Fraction(1), Fraction(40), "lb")),
     ("4/1 GAL", Pack(Fraction(4), Fraction(1), "gal")), ("12/32 OZ", Pack(Fraction(12), Fraction(32), "oz")),
     ("6/#10", Pack(Fraction(6), Fraction(1), "#10")), ("6/10#", Pack(Fraction(6), Fraction(10), "lb")),
     ("24 CT", Pack(Fraction(1), Fraction(24), "each")), ("4/5 LB CS", Pack(Fraction(4), Fraction(5), "lb"))],
)
def test_parse_pack(text, pack):
    assert parse_pack(text) == pack


def test_can_size_and_pound_sign_are_not_confused():
    assert parse_pack("6/#10").unit == "#10"   # six #10 cans: a volume
    assert parse_pack("6/10#").unit == "lb"    # six 10-lb bags: a weight


@pytest.mark.parametrize("text", ["", "case", "4/", "0/5 LB", "4/0 LB", "4/5 PALLET"])
def test_unreadable_packs_refuse(text):
    assert is_refusal(parse_pack(text))


def test_pack_quantity():
    assert pack_quantity(parse_pack("4/5 LB"), "lb") == 20
    assert pack_quantity(parse_pack("4/5 LB"), "oz") == 320
    assert pack_quantity(parse_pack("4/1 GAL"), "qt") == 16
    assert pack_quantity(parse_pack("6/#10"), "qt") == pytest.approx(6 * 3.375)
    assert is_refusal(pack_quantity(parse_pack("6/#10"), "lb"))   # a can size needs a volume ingredient
    assert is_refusal(pack_quantity(parse_pack("4/5 LB"), "qt"))  # weight to volume


# ---- costs
def test_case_price_to_unit_cost():
    assert unit_cost_from_case(38.0, parse_pack("4/5 LB"), "lb") == pytest.approx(1.90)
    assert unit_cost_from_case(38.0, parse_pack("4/5 LB"), "oz") == pytest.approx(1.90 / 16)
    assert unit_cost_from_case(30.0, parse_pack("4/1 GAL"), "qt") == pytest.approx(30 / 16)
    assert unit_cost_from_case(54.0, parse_pack("6/#10"), "qt") == pytest.approx(54 / (6 * 3.375))
    assert unit_cost_from_case(12.0, parse_pack("24 CT"), "each") == pytest.approx(0.5)
    assert unit_cost_from_case(60.0, parse_pack("2 DOZ"), "doz") == pytest.approx(30.0)


def test_case_price_refusals():
    assert is_refusal(unit_cost_from_case(0.0, parse_pack("4/5 LB"), "lb"))
    assert is_refusal(unit_cost_from_case(-5.0, parse_pack("4/5 LB"), "lb"))
    assert unit_cost_from_case(5.0, parse_pack("4/5 LB"), "lb") == pytest.approx(0.25)
    assert unit_cost_from_case(38.0, parse_pack("4/5 LB"), "qt").code == "unconvertible_unit"
    assert unit_cost_from_case(0.0, parse_pack("4/5 LB"), "lb").code == "needs_cost"


def test_unit_price_conversion():
    assert unit_cost_from_unit_price(4.80, "lb", "lb") == pytest.approx(4.80)
    assert unit_cost_from_unit_price(4.80, "lb", "oz") == pytest.approx(0.30)   # $/lb to $/oz divides by 16
    assert unit_cost_from_unit_price(16.0, "gal", "qt") == pytest.approx(4.0)
    assert unit_cost_from_unit_price(6.0, "doz", "each") == pytest.approx(0.5)
    assert is_refusal(unit_cost_from_unit_price(4.80, "lb", "qt"))
    assert is_refusal(unit_cost_from_unit_price(0, "lb", "lb"))


def test_catch_weight_uses_received_weight_not_case_count():
    # 2 cases ordered (about 80 lb), 78.4 lb received, billed $352.80: $4.50 per lb
    assert unit_cost_catch_weight(352.80, 78.4, "lb", "lb") == pytest.approx(4.50)
    assert unit_cost_catch_weight(352.80, 78.4, "lb", "oz") == pytest.approx(4.50 / 16)
    assert is_refusal(unit_cost_catch_weight(352.80, 0, "lb", "lb"))
    assert is_refusal(unit_cost_catch_weight(352.80, 78.4, "lb", "each"))


# ---- line total
def test_line_total_check_tolerance():
    ok = check_line_total(2, 19.99, 39.98)
    assert ok.ok and ok.expected == pytest.approx(39.98)
    assert check_line_total(2, 19.99, 40.00).ok          # one cent apart: within $0.02
    assert not check_line_total(2, 19.99, 41.00).ok
    assert check_line_total(1000, 1.0, 1004.0).ok         # 0.4% of 1004: within 0.5%
    assert not check_line_total(1000, 1.0, 1010.0).ok
    bad = check_line_total(3, 10.0, 25.0)
    assert not bad.ok and bad.expected == 30.0 and bad.stated == 25.0


def test_price_strings():
    assert parse_price("$1,234.50") == pytest.approx(1234.50)
    assert parse_price("12.99") == pytest.approx(12.99)
    assert parse_price("($45.00)") == pytest.approx(-45.0)   # a credit
    assert parse_price("-45.00") == pytest.approx(-45.0)
    assert is_refusal(parse_price("call for price"))
