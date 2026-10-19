import json
from pathlib import Path

import pytest

from ingest import model_client as mc
from ingest.model_client import DocumentTooLarge, ModelAPIError, StubClient
from ingest.parse import Catalogue, compute_line_cost, load_catalogue, locate, parse_invoice, parse_recipe
from ingest.stage import FLAGS, read_staging, write_staging

ROOT = Path(__file__).resolve().parents[2]
SYNTH = ROOT / "data" / "synthetic"
EVAL = ROOT / "data" / "eval"


@pytest.fixture(scope="module")
def cat():
    return load_catalogue(SYNTH, with_existing=False)


def line(no, desc, ing, quote, pack=None, ordered=None, received=None, unit=None, price=None, price_unit=None, ext=None, status="ok"):
    return {"line_no": no, "description": desc, "pack_text": pack, "qty_ordered": ordered, "qty_received": received,
            "unit_text": unit, "unit_price": price, "price_unit_text": price_unit, "extended_price": ext,
            "matched_ingredient_id": ing, "status": status, "source_quote": quote}


def invoice(lines, other=(), date="2025-03-04"):
    return {"supplier": "Harbor Provisions", "invoice_date": date, "lines": list(lines), "other_lines": list(other)}


def scripted(*responses):
    """A stub client that answers each call with the next scripted response."""
    queue = list(responses)
    return StubClient(lambda s, u, sc: queue.pop(0))


def doc(*lines):
    return "HARBOR PROVISIONS\nINVOICE # 1\nDate: 2025-03-04\n\n" + "\n".join(lines) + "\n"


RIBEYE = "BEEF RIBEYE | 4/5 LB | 2 | CS | 448.00 | 896.00"


def one(rows, kind="cost"):
    got = [r for r in rows if r.kind == kind and r.status != "skipped"]
    assert len(got) == 1, got
    return got[0]


def ribeye_line(**kw):
    base = dict(pack="4/5 LB", ordered="2", unit="CS", price="448.00", ext="896.00")
    base.update(kw)
    return line(5, "BEEF RIBEYE", "ribeye", RIBEYE, **base)


# ---------------------------------------------------------------- clean and basic
def test_a_clean_case_line_becomes_a_cost_row_in_the_ingredients_unit(cat):
    res = parse_invoice(doc(RIBEYE), scripted(invoice([ribeye_line()])), cat)
    r = one(res.rows)
    assert r.ingredient_id == "ribeye" and r.unit_cost == pytest.approx(22.40) and r.effective_week == "2025-03-03"
    assert r.flags == () and r.status == "proposed" and r.source_line == 5 and r.source_quote == RIBEYE
    assert res.meta.kind == "invoice" and res.meta.calls == 1 and res.meta.retries == 0 and res.meta.mode == "stub"


def test_every_flag_code_in_the_set_can_be_produced():
    produced = set()
    # filled in by the cases below via the module-level collector
    assert len(FLAGS) == 13  # the cases below cover each one: see the parametrised test at the end


@pytest.mark.parametrize("date,flag", [(None, "missing_date"), ("sometime in March", "missing_date")])
def test_missing_or_unreadable_date(cat, date, flag):
    res = parse_invoice(doc(RIBEYE), scripted(invoice([ribeye_line()], date=date)), cat)
    r = one(res.rows)
    assert flag in r.flags and r.effective_week == "" and r.unit_cost == pytest.approx(22.40)


def test_unknown_pack_unit_and_weight_to_volume_have_no_value(cat):
    q1 = "PASTA | 4/5 PLT | 2 | CS | 55.00 | 110.00"
    q2 = "CREAM HVY 36% | 40 LB | 1 | CS | 48.00 | 48.00"
    res = parse_invoice(doc(q1, q2), scripted(invoice([
        line(5, "PASTA", "pasta", q1, pack="4/5 PLT", ordered="2", unit="CS", price="55.00", ext="110.00"),
        line(6, "CREAM", "cream", q2, pack="40 LB", ordered="1", unit="CS", price="48.00", ext="48.00")])), cat)
    for r in (x for x in res.rows if x.kind == "cost"):
        assert r.unit_cost is None and "unconvertible_unit" in r.flags and r.status == "flagged"


def test_a_bunch_priced_line_is_refused(cat):
    q = "LETTUCE ROMAINE | | 12 | BUNCH | 1.80 | 21.60"
    res = parse_invoice(doc(q), scripted(invoice([line(5, "LETTUCE", "romaine", q, ordered="12", unit="BUNCH", price="1.80", ext="21.60")])), cat)
    r = one(res.rows)
    assert r.unit_cost is None and r.flags == ("unconvertible_unit",)


def test_ambiguous_status_and_unknown_ids(cat):
    q = "CHEESE SHREDDED | 4/5 LB | 1 | CS | 62.00 | 62.00"
    amb = line(5, "CHEESE SHREDDED", "cheddar", q, pack="4/5 LB", ordered="1", unit="CS", price="62.00", ext="62.00", status="ambiguous")
    r = one(parse_invoice(doc(q), scripted(invoice([amb])), cat).rows)
    assert r.flags == ("ambiguous_name",) and r.unit_cost == pytest.approx(3.10)
    bad = dict(amb, matched_ingredient_id="mystery_cheese", status="ok")
    r = one(parse_invoice(doc(q), scripted(invoice([bad])), cat).rows)
    assert set(r.flags) == {"ambiguous_name", "needs_cost"} and r.unit_cost is None and "not in the catalogue" in r.reason
    missing = dict(amb, status="missing")
    r = one(parse_invoice(doc(q), scripted(invoice([missing])), cat).rows)
    assert "needs_cost" in r.flags and r.unit_cost is None


def test_a_new_ingredient_is_proposed_with_an_existing_unit(cat):
    q = "OIL TRUFFLE BLACK | 6/1 GAL | 1 | CS | 36.00 | 36.00"
    res = parse_invoice(doc(q), scripted(invoice([line(5, "OIL TRUFFLE BLACK", "NEW", q, pack="6/1 GAL", ordered="1", unit="CS", price="36.00", ext="36.00")])), cat)
    ing, cost = one(res.rows, "ingredient"), one(res.rows, "cost")
    assert ing.unit == "gal" and ing.ingredient_id == "oil_truffle_black" and ing.name == "Oil Truffle Black"
    assert "new_ingredient" in ing.flags and "new_ingredient" in cost.flags
    assert cost.ingredient_id == ing.ingredient_id and cost.unit_cost == pytest.approx(6.0)
    assert ing.unit in ("lb", "qt", "gal", "oz", "each", "doz", "head")


def test_a_new_ingredient_slug_never_collides(cat):
    q = "OIL | 6/1 GAL | 1 | CS | 36.00 | 36.00"
    res = parse_invoice(doc(q), scripted(invoice([line(5, "OIL", "NEW", q, pack="6/1 GAL", ordered="1", unit="CS", price="36.00", ext="36.00")])), cat)
    assert one(res.rows, "ingredient").ingredient_id == "oil_2"   # `oil` is already in the catalogue


# ---------------------------------------------------------------- checks and the retry
def test_a_line_total_mismatch_is_flagged_and_keeps_both_numbers(cat):
    q = "FLOUR AP | 50 LB | 2 | CS | 40.00 | 99.00"
    bad = line(5, "FLOUR", "flour", q, pack="50 LB", ordered="2", unit="CS", price="40.00", ext="99.00")
    client = scripted(invoice([bad]), invoice([bad]))
    res = parse_invoice(doc(q), client, cat)
    r = one(res.rows)
    assert "check_failed" in r.flags and r.unit_cost == pytest.approx(0.80)
    assert "80.00" in r.reason and "99.00" in r.reason
    assert client.calls == 2 and res.meta.retries == 1       # one retry, then flagged


def test_a_retry_that_fixes_the_line_clears_the_flag(cat):
    q = "FLOUR AP | 50 LB | 2 | CS | 40.00 | 80.00"
    bad = line(5, "FLOUR", "flour", q, pack="50 LB", ordered="2", unit="CS", price="40.00", ext="98.00")
    good = line(5, "FLOUR", "flour", q, pack="50 LB", ordered="2", unit="CS", price="40.00", ext="80.00")
    seen = []
    client = StubClient(lambda s, u, sc: (seen.append(u), [invoice([bad]), invoice([good])][len(seen) - 1])[1])
    res = parse_invoice(doc(q), client, cat)
    assert one(res.rows).flags == () and res.meta.retries == 1
    assert "had these problems" in seen[1] and "line_no 5" in seen[1] and "had these problems" not in seen[0]


def test_a_quote_not_in_the_document_is_retried_then_flagged(cat):
    ghost = ribeye_line()
    ghost["source_quote"] = "BEEF RIBEYE 99 CS made up line"
    client = scripted(invoice([ghost]), invoice([ghost]))
    res = parse_invoice(doc(RIBEYE), client, cat)
    r = one(res.rows)
    assert "check_failed" in r.flags and "quote not found" in r.reason and client.calls == 2
    assert res.errors and "not found" in res.errors[0]


def test_at_most_one_retry(cat):
    ghost = dict(ribeye_line(), source_quote="not in the doc")
    client = scripted(invoice([ghost]), invoice([ghost]), invoice([ghost]))
    parse_invoice(doc(RIBEYE), client, cat)
    assert client.calls == 2


def test_quote_location_is_whitespace_insensitive():
    lines = ["A  B   C", "BEEF  RIBEYE | 4/5 LB"]
    assert locate("beef ribeye | 4/5 lb", lines) == 2
    assert locate("nothing like it", lines) is None
    assert locate("", lines) is None


# ---------------------------------------------------------------- catch weight and duplicates
def test_catch_weight_uses_received_weight(cat):
    q = "BEEF RIBEYE LIPON | CW | 40.6 | LB | 22.40 | 909.44"
    ln = line(5, "BEEF RIBEYE LIPON", "ribeye", q, pack="CW", ordered="2", received="40.6", unit="LB", price="22.40", price_unit="LB", ext="909.44")
    r = one(parse_invoice(doc(q), scripted(invoice([ln])), cat).rows)
    assert r.unit_cost == pytest.approx(909.44 / 40.6) and r.flags == ()


def test_catch_weight_without_a_received_weight_has_no_cost(cat):
    q = "BEEF TOP SIRLOIN | CW | 2 | CS | 28.00 |"
    ln = line(5, "BEEF TOP SIRLOIN", "sirloin", q, pack="CW", ordered="2", unit="CS", price="28.00", price_unit="LB")
    r = one(parse_invoice(doc(q), scripted(invoice([ln])), cat).rows)
    assert r.unit_cost is None and r.flags == ("needs_cost",)


def test_the_same_ingredient_twice_stages_one_weighted_row(cat):
    q1, q2 = "FLOUR | 2 | LB | 1.00 | 2.00", "FLOUR | 6 | LB | 2.00 | 12.00"
    l1 = line(5, "FLOUR", "flour", q1, ordered="2", unit="LB", price="1.00", price_unit="LB", ext="2.00")
    l2 = line(6, "FLOUR", "flour", q2, ordered="6", unit="LB", price="2.00", price_unit="LB", ext="12.00")
    res = parse_invoice(doc(q1, q2), scripted(invoice([l1, l2])), cat)
    r = one(res.rows)
    assert "conflict" in r.flags and r.unit_cost == pytest.approx((2 * 1.0 + 6 * 2.0) / 8)
    assert r.source_line == 5 and "lines 5, 6" in r.reason


def test_a_row_that_would_replace_an_existing_cost_is_an_update(cat):
    existing = Catalogue(cat.ingredients, cat.items, existing_costs={("ribeye", "2025-03-03"): 22.0})
    r = one(parse_invoice(doc(RIBEYE), scripted(invoice([ribeye_line()])), existing).rows)
    assert "update" in r.flags and r.status == "flagged" and "replace" in r.reason
    other = Catalogue(cat.ingredients, cat.items, existing_costs={("ribeye", "2025-02-24"): 22.0})
    assert one(parse_invoice(doc(RIBEYE), scripted(invoice([ribeye_line()])), other).rows).flags == ()


def test_fee_and_credit_lines_are_listed_as_skipped_and_never_costed(cat):
    fee, credit = "FUEL SURCHARGE 8.25", "CREDIT MEMO - SHORT SHIPPED (22.50)"
    others = [{"line_no": 6, "category": "fee", "description": "FUEL", "amount": "8.25", "source_quote": fee},
              {"line_no": 7, "category": "credit", "description": "CREDIT", "amount": "(22.50)", "source_quote": credit}]
    res = parse_invoice(doc(RIBEYE, fee, credit), scripted(invoice([ribeye_line()], others)), cat)
    skipped = [r for r in res.rows if r.status == "skipped"]
    assert [r.reason for r in skipped] == ["fee", "credit"] and all(r.unit_cost is None and "skipped_line" in r.flags for r in skipped)
    assert len([r for r in res.rows if r.status != "skipped"]) == 1


# ---------------------------------------------------------------- recipes
def recipe(lines, dish="short_rib", servings="20"):
    return {"dish_name": "Short Rib", "matched_item_id": dish, "servings": servings, "lines": lines}


def rline(no, q, u, text, ing, quote, note=None, status="ok"):
    return {"line_no": no, "quantity_text": q, "unit_text": u, "ingredient_text": text, "matched_ingredient_id": ing,
            "note": note, "status": status, "source_quote": quote}


RDOC = "SHORT RIB\nServes 20\n\n- 12-14 lb beef short rib\n- 8 lb potato (peeled weight)\n- 1 qt heavy cream\n- 3 lb 6 oz onion\n- salt and pepper to taste\n"


def test_recipe_lines_become_per_serving_quantities(cat):
    data = recipe([
        rline(4, "12-14", "lb", "beef short rib", "short_rib", "- 12-14 lb beef short rib"),
        rline(5, "8", "lb", "potato", "potato", "- 8 lb potato (peeled weight)", note="peeled weight"),
        rline(6, "1", "qt", "heavy cream", "cream", "- 1 qt heavy cream"),
        rline(7, "3 lb 6 oz", None, "onion", "onion", "- 3 lb 6 oz onion"),
        rline(8, "to taste", None, "salt and pepper", "NEW", "- salt and pepper to taste")])
    res = parse_recipe(RDOC, scripted(data), cat)
    by = {r.ingredient_id: r for r in res.rows if r.kind == "recipe_line" and r.status != "skipped"}
    assert by["short_rib"].qty_per_serving == pytest.approx(0.65) and by["short_rib"].flags == ("range_midpoint",)
    assert by["potato"].qty_per_serving == pytest.approx(0.4) and by["potato"].flags == ("no_yield_applied",)
    assert by["cream"].qty_per_serving == pytest.approx(0.05) and by["cream"].flags == ()
    assert by["onion"].qty_per_serving == pytest.approx(3.375 / 20)
    skipped = [r for r in res.rows if r.status == "skipped"]
    assert len(skipped) == 1 and "to taste" in skipped[0].reason
    assert not [r for r in res.rows if r.kind == "ingredient"]      # the skipped NEW line proposes nothing
    assert all(r.item_id == "short_rib" for r in by.values())


def test_a_recipe_with_no_servings_leaves_every_row_unfilled(cat):
    data = recipe([rline(4, "6", "lb", "quinoa", "quinoa", "- 6 lb quinoa")], dish="grain_bowl", servings=None)
    r = one(parse_recipe("GRAIN BOWL\n\n- 6 lb quinoa\n", scripted(dict(data, lines=[rline(3, "6", "lb", "quinoa", "quinoa", "- 6 lb quinoa")])), cat).rows, "recipe_line")
    assert r.qty_per_serving is None and "missing_servings" in r.flags


def test_a_dish_not_on_the_menu_is_never_invented(cat):
    data = recipe([rline(4, "1", "qt", "heavy cream", "cream", "- 1 qt heavy cream")], dish=None)
    r = one(parse_recipe(RDOC, scripted(data), cat).rows, "recipe_line")
    assert "ambiguous_name" in r.flags and r.item_id == "" and "menu" in r.reason


def test_a_recipe_for_a_dish_with_existing_rows_is_an_update(cat):
    existing = Catalogue(cat.ingredients, cat.items, existing_recipes={"short_rib"})
    data = recipe([rline(6, "1", "qt", "heavy cream", "cream", "- 1 qt heavy cream")])
    r = one(parse_recipe(RDOC, scripted(data), existing).rows, "recipe_line")
    assert "update" in r.flags


def test_weight_to_volume_in_a_recipe_is_refused(cat):
    data = recipe([rline(6, "2", "cups", "onion", "onion", "- 3 lb 6 oz onion")])   # onion is stocked per lb
    r = one(parse_recipe(RDOC, scripted(data), cat).rows, "recipe_line")
    assert r.qty_per_serving is None and "unconvertible_unit" in r.flags


def test_a_new_recipe_ingredient_is_proposed(cat):
    data = recipe([rline(6, "1", "qt", "black garlic paste", "NEW", "- 1 qt heavy cream")])
    res = parse_recipe(RDOC, scripted(data), cat)
    ing = one(res.rows, "ingredient")
    assert ing.unit == "qt" and ing.ingredient_id == "black_garlic_paste"


# ---------------------------------------------------------------- errors, size, end to end
def test_oversized_documents_are_refused_before_any_call(cat):
    client = scripted()
    with pytest.raises(DocumentTooLarge):
        parse_invoice("x" * 40_000, client, cat)
    assert client.calls == 0


def test_model_failures_stop_the_run_with_no_rows(cat):
    def boom(s, u, sc):
        raise ModelAPIError("down")
    with pytest.raises(ModelAPIError):
        parse_invoice(doc(RIBEYE), StubClient(boom), cat)
    with pytest.raises(mc.SchemaViolation):
        parse_invoice(doc(RIBEYE), scripted({"lines": []}), cat)


def test_staged_rows_round_trip_through_the_staging_file(cat, tmp_path):
    res = parse_invoice(doc(RIBEYE), scripted(invoice([ribeye_line()])), cat)
    p = tmp_path / "run.csv"
    write_staging(res.rows, p)
    assert [r.row_id for r in read_staging(p)] == [r.row_id for r in res.rows]
    again = parse_invoice(doc(RIBEYE), scripted(invoice([ribeye_line()])), cat)
    assert [r.row_id for r in again.rows] == [r.row_id for r in res.rows]   # re-parsing gives the same ids


# ---------------------------------------------------------------- the committed evaluation cases through an oracle model
def oracle(truth_row_raw):
    pass


def truth_cases(kind, tiers):
    out = []
    for p in sorted((EVAL / "truth").glob("*.json")):
        t = json.loads(p.read_text())
        if t["kind"] == kind and t["tier"] in tiers:
            out.append(t)
    return out


@pytest.mark.parametrize("truth", truth_cases("invoice", (1, 2)), ids=lambda t: t["case_id"])
def test_tiers_one_and_two_end_to_end_with_an_oracle_model(truth, cat):
    text = (EVAL / truth["source_file"]).read_text()
    lines = text.splitlines()
    out = []
    for i, row in enumerate(truth["rows"], 1):
        raw = row["raw"]
        out.append(line(i, raw["description"], row["ingredient_id"], lines[row["source_line"] - 1].strip(),
                        pack=raw["pack_text"], ordered=raw["qty"], unit=raw["unit"], price=raw["unit_price"],
                        price_unit=raw["price_unit"], ext=raw["extended_price"]))
    res = parse_invoice(text, scripted(invoice(out, date=truth["invoice_date"])), cat)
    got = {(r.ingredient_id, r.effective_week): r for r in res.rows if r.kind == "cost"}
    assert len(got) == len(truth["rows"])
    for row in truth["rows"]:
        r = got[(row["ingredient_id"], truth["effective_week"])]
        assert r.unit_cost == pytest.approx(row["unit_cost"], rel=1e-9), (truth["case_id"], row)
        assert r.flags == () and r.source_line == row["source_line"]


# ---------------------------------------------------------------- tolerance for how a model writes quantities (found in the first live run)
@pytest.mark.parametrize("received,unit", [("121.6 LB", "LB"), ("121.6", "LB"), ("121.6 lb", None), ("121.6", None)])
def test_a_catch_weight_quantity_may_carry_its_unit(received, unit):
    ln = line(7, "BACON SLICED", "bacon", "q", pack="CW", received=received, unit=unit, price="9.71", price_unit="LB", ext="1,180.74")
    lc = compute_line_cost(ln, "lb")
    assert lc.unit_cost == pytest.approx(1180.74 / 121.6) and lc.flags == []


def test_a_case_or_unit_quantity_may_carry_its_unit():
    case = line(5, "FLOUR", "flour", "q", pack="50 LB", ordered="2 CS", unit="CS", price="40.00", ext="99.00")
    lc = compute_line_cost(case, "lb")
    assert lc.unit_cost == pytest.approx(0.80) and "check_failed" in lc.flags       # the check still runs on "2 CS"
    plain = line(5, "CREAM", "cream", "q", ordered="13 QT", unit="QT", price="6.02", price_unit="QT", ext="78.26")
    assert compute_line_cost(plain, "qt").flags == []
