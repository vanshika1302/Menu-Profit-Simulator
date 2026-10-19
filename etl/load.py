"""Create the raw tables and load the synthetic CSVs.

Ground truth goes into the validation schema and nowhere else.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

from etl.warehouse import ROOT, SQL_DIR

DATA_DIR = ROOT / "data" / "synthetic"
APPROVED_DIR = ROOT / "data" / "approved"
RAW_TABLES = ["menu_items", "ingredients", "recipes", "ingredient_costs", "weekly_sales"]


def merge_approved(con: duckdb.DuckDBPyConnection, approved_dir: Path) -> None:
    """Merge the person-approved overlay over the loaded base (opt-in; see ingest/apply.py).

    A cost row for the same ingredient and week replaces the base row; an approved recipe replaces every
    base row for its dish; new ingredients are appended (an existing id keeps the base row).
    """
    approved_dir = Path(approved_dir)
    f = {name: approved_dir / f"{name}.csv" for name in ("ingredients", "ingredient_costs", "recipes")}
    if f["ingredients"].exists():
        con.execute(f"INSERT INTO raw_ingredients BY NAME SELECT DISTINCT ON (o.ingredient_id) o.* FROM read_csv('{f['ingredients'].as_posix()}', header = true) o "
                    "WHERE o.ingredient_id NOT IN (SELECT ingredient_id FROM raw_ingredients)")
    if f["ingredient_costs"].exists():
        src = f"read_csv('{f['ingredient_costs'].as_posix()}', header = true)"
        con.execute(f"DELETE FROM raw_ingredient_costs WHERE (ingredient_id, effective_week) IN (SELECT ingredient_id, CAST(effective_week AS DATE) FROM {src})")
        con.execute(f"INSERT INTO raw_ingredient_costs BY NAME SELECT * FROM {src}")
    if f["recipes"].exists():
        src = f"read_csv('{f['recipes'].as_posix()}', header = true)"
        con.execute(f"DELETE FROM raw_recipes WHERE item_id IN (SELECT item_id FROM {src})")
        con.execute(f"INSERT INTO raw_recipes BY NAME SELECT * FROM {src}")


def load_all(con: duckdb.DuckDBPyConnection, data_dir: Path = DATA_DIR, with_approved: bool = False,
             approved_dir: Path = APPROVED_DIR) -> None:
    """Rebuild schema, load every CSV (and, only if asked, the approved overlay), then create the views."""
    for view in con.execute("SELECT view_name FROM duckdb_views() WHERE NOT internal").fetchall():
        con.execute(f'DROP VIEW IF EXISTS "{view[0]}"')
    con.execute("DROP TABLE IF EXISTS validation.ground_truth")
    for t in RAW_TABLES + ["config"]:
        con.execute(f"DROP TABLE IF EXISTS {'raw_' + t if t in RAW_TABLES else t}")
    con.execute("DROP SCHEMA IF EXISTS validation")
    con.execute((SQL_DIR / "schema.sql").read_text())
    for t in RAW_TABLES:
        path = (data_dir / f"{t}.csv").as_posix()
        con.execute(f"INSERT INTO raw_{t} BY NAME SELECT * FROM read_csv('{path}', header = true)")
    gt = data_dir / "ground_truth.csv"
    if gt.exists():  # the simulator never needs it; validation tables stay empty without it
        con.execute(f"INSERT INTO validation.ground_truth BY NAME SELECT * FROM read_csv('{gt.as_posix()}', header = true)")
    if with_approved:
        merge_approved(con, approved_dir)
    con.execute((SQL_DIR / "views.sql").read_text())
