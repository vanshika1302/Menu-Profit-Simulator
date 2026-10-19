"""Generator checks: determinism, schemas, size, sanity, class coverage."""
import filecmp
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from etl.generate import generate

SCHEMAS = {
    "menu_items": ["item_id", "name", "category", "base_price"],
    "ingredients": ["ingredient_id", "name", "unit"],
    "recipes": ["item_id", "ingredient_id", "qty_per_serving"],
    "ingredient_costs": ["ingredient_id", "effective_week", "unit_cost"],
    "weekly_sales": ["week_start", "item_id", "units_sold", "avg_selling_price"],
    "ground_truth": ["item_id", "category", "true_elasticity", "within_category_switch_share", "cross_category_switch_share"],
}


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("synthetic")
    tables = generate(out)
    return out, tables


def test_same_seed_identical_csvs(built, tmp_path):
    out, _ = built
    generate(tmp_path)
    for name in SCHEMAS:
        assert filecmp.cmp(out / f"{name}.csv", tmp_path / f"{name}.csv", shallow=False)


def test_committed_csvs_match_generator(built):
    out, _ = built
    committed = Path(__file__).resolve().parents[1] / "data" / "synthetic"
    for name in SCHEMAS:
        assert filecmp.cmp(out / f"{name}.csv", committed / f"{name}.csv", shallow=False)


def test_schemas(built):
    _, t = built
    for name, cols in SCHEMAS.items():
        assert list(t[name].columns) == cols


def test_shape(built):
    _, t = built
    assert len(t["menu_items"]) == 30
    assert t["menu_items"].category.nunique() == 6
    assert 30 <= len(t["ingredients"]) <= 50
    assert len(t["weekly_sales"]) == 52 * 30
    beef = {"ribeye", "sirloin", "short_rib", "ground_beef", "shaved_beef"}
    r = t["recipes"]
    assert r[r.ingredient_id.isin(beef)].item_id.nunique() == 7


def test_size(built):
    out, _ = built
    assert sum(f.stat().st_size for f in out.glob("*.csv")) < 500_000


def test_no_negatives(built):
    _, t = built
    assert (t["weekly_sales"].units_sold >= 0).all()
    assert (t["weekly_sales"].avg_selling_price > 0).all()
    assert (t["ingredient_costs"].unit_cost > 0).all()


def test_price_history(built):
    _, t = built
    ws = t["weekly_sales"]
    base = t["menu_items"].set_index("item_id").base_price
    changed = ws[ws.avg_selling_price != ws.item_id.map(base)].item_id.unique()
    assert 5 <= len(changed) <= 8  # 4-5 rises plus promos, with overlap


def _unit_costs(t):
    ic = t["ingredient_costs"].sort_values("effective_week").groupby("ingredient_id").last().unit_cost
    r = t["recipes"].copy()
    r["c"] = r.qty_per_serving * r.ingredient_id.map(ic)
    return r.groupby("item_id").c.sum()


def _trailing(t):
    ws = t["weekly_sales"]
    wk = sorted(ws.week_start.unique())[-12:]
    g = ws[ws.week_start.isin(wk)].groupby("item_id").agg(units=("units_sold", "sum"), price=("avg_selling_price", "last"))
    g["category"] = t["menu_items"].set_index("item_id").category
    g["cost"] = _unit_costs(t)
    g["cm"] = g.price - g.cost
    return g


def test_food_cost_range(built):
    _, t = built
    g = _trailing(t)
    fc = g.cost / g.price
    assert fc.between(0.20, 0.45).all(), fc[~fc.between(0.20, 0.45)]


def _classify(g):
    n = len(g)
    share = g.units / g.units.sum()
    hi = g.cm >= (g.cm * g.units).sum() / g.units.sum()
    pop = share >= 0.7 / n
    return pd.Series(np.where(pop & hi, "Star", np.where(pop, "Plowhorse", np.where(hi, "Puzzle", "Dog"))), index=g.index)


def test_all_four_classes_appear(built):
    _, t = built
    g = _trailing(t)
    assert (g.units >= 50).all()
    whole = _classify(g).value_counts()
    assert set(whole.index) == {"Star", "Plowhorse", "Puzzle", "Dog"}
    per_cat = pd.concat([_classify(x) for _, x in g.groupby("category")]).value_counts()
    assert set(per_cat.index) == {"Star", "Plowhorse", "Puzzle", "Dog"}


def test_ground_truth_ranges(built):
    _, t = built
    gt = t["ground_truth"]
    assert (gt.true_elasticity < 0).all()
    assert gt.within_category_switch_share.between(0.30, 0.50).all()
