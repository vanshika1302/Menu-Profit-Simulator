"""Cross-check every SQL view against an independent pandas computation on the same CSVs."""
import numpy as np
import pandas as pd
import pytest

from etl.load import DATA_DIR, load_all
from etl.warehouse import get_connection

WINDOW, MIN_UNITS, FACTOR = 12, 50, 0.7


@pytest.fixture(scope="module")
def con():
    c = get_connection(":memory:")
    load_all(c)
    yield c
    c.close()


@pytest.fixture(scope="module")
def csv():
    names = ["menu_items", "ingredients", "recipes", "ingredient_costs", "weekly_sales"]
    return {n: pd.read_csv(DATA_DIR / f"{n}.csv") for n in names}


@pytest.fixture(scope="module")
def expected(csv):
    ic = csv["ingredient_costs"].sort_values("effective_week").groupby("ingredient_id").last().unit_cost
    r = csv["recipes"].assign(c=lambda d: d.qty_per_serving * d.ingredient_id.map(ic))
    cost = r.groupby("item_id").c.sum()
    ws = csv["weekly_sales"]
    weeks = sorted(ws.week_start.unique())[-WINDOW:]
    w = ws[ws.week_start.isin(weeks)]
    df = w.groupby("item_id").units_sold.sum().rename("window_units").to_frame()
    df["price"] = w[w.week_start == weeks[-1]].set_index("item_id").avg_selling_price
    df["unit_cost"] = cost
    df["cm"] = df.price - df.unit_cost
    df["category"] = csv["menu_items"].set_index("item_id").category
    return df, ic, cost


def test_latest_ingredient_cost(con, expected):
    _, ic, _ = expected
    got = con.execute("SELECT * FROM v_latest_ingredient_cost").df().set_index("ingredient_id").unit_cost
    pd.testing.assert_series_equal(got.sort_index(), ic.sort_index(), check_names=False)


def test_item_cost(con, expected):
    _, _, cost = expected
    got = con.execute("SELECT * FROM v_item_cost").df().set_index("item_id").unit_cost
    pd.testing.assert_series_equal(got.sort_index(), cost.sort_index(), check_names=False)


def test_window_weeks(con, csv):
    got = con.execute("SELECT week_start FROM v_window_weeks").df().week_start
    want = sorted(csv["weekly_sales"].week_start.unique())[-WINDOW:]
    assert sorted(got.dt.strftime("%Y-%m-%d")) == want


def test_item_cm(con, expected):
    df, _, _ = expected
    got = con.execute("SELECT * FROM v_item_cm").df().set_index("item_id").sort_index()
    df = df.sort_index()
    assert len(got) == 30
    for col in ["window_units", "price", "unit_cost", "cm"]:
        np.testing.assert_allclose(got[col], df[col], rtol=1e-12)
    np.testing.assert_allclose(got.weekly_units, df.window_units / WINDOW)
    np.testing.assert_allclose(got.food_cost_pct, df.unit_cost / df.price)
    np.testing.assert_allclose(got.weekly_contribution_profit, df.window_units / WINDOW * df.cm)
    assert (got.insufficient_data == (df.window_units < MIN_UNITS)).all()


def _pandas_matrix(df, scope):
    out = []
    groups = df.groupby("category") if scope == "category" else [("menu", df)]
    for key, g in groups:
        ok = g[g.window_units >= MIN_UNITS]
        n, total = len(ok), ok.window_units.sum()
        out.append(
            ok.assign(
                scope_key=key,
                unit_share=ok.window_units / total,
                popularity_threshold=FACTOR / n,
                margin_threshold=(ok.window_units * ok.cm).sum() / total,
            )
        )
    return pd.concat(out)


@pytest.mark.parametrize("scope", ["category", "menu"])
def test_matrix_inputs(con, expected, scope):
    df, _, _ = expected
    want = _pandas_matrix(df, scope).sort_index()
    got = con.execute("SELECT * FROM v_matrix_inputs WHERE scope = ? AND insufficient_data = 0", [scope]).df()
    got = got.set_index("item_id").sort_index()
    assert list(got.index) == list(want.index)
    for col in ["unit_share", "popularity_threshold", "margin_threshold"]:
        np.testing.assert_allclose(got[col], want[col], rtol=1e-12)
    assert (got.scope_key == want.scope_key).all()
    # shares sum to one inside each scope group
    np.testing.assert_allclose(got.groupby("scope_key").unit_share.sum(), 1.0)


def test_insufficient_data_excluded(con):
    """Raise the minimum above some items' volume: they lose a class and leave the thresholds."""
    con.execute("UPDATE config SET min_units = 700")
    try:
        rows = con.execute("SELECT * FROM v_matrix_inputs WHERE scope = 'menu'").df()
        low = rows[rows.insufficient_data == 1]
        assert len(low) > 0
        assert low.unit_share.isna().all() and low.margin_threshold.isna().all()
        ok = rows[rows.insufficient_data == 0]
        assert np.isclose(ok.unit_share.sum(), 1.0)
        assert np.allclose(ok.popularity_threshold, FACTOR / len(ok))
    finally:
        con.execute("UPDATE config SET min_units = 50")


def test_ground_truth_only_in_validation_schema(con):
    tables = con.execute(
        "SELECT table_schema, table_name FROM information_schema.tables WHERE table_name LIKE '%truth%'"
    ).fetchall()
    assert tables == [("validation", "ground_truth")]
    views = con.execute("SELECT sql FROM duckdb_views() WHERE NOT internal").fetchall()
    assert not any("validation" in v[0] or "ground_truth" in v[0] for v in views)
