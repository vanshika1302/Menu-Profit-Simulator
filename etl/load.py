"""Create the raw tables and load the synthetic CSVs.

Ground truth goes into the validation schema and nowhere else.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

from etl.warehouse import ROOT, SQL_DIR

DATA_DIR = ROOT / "data" / "synthetic"
RAW_TABLES = ["menu_items", "ingredients", "recipes", "ingredient_costs", "weekly_sales"]


def load_all(con: duckdb.DuckDBPyConnection, data_dir: Path = DATA_DIR) -> None:
    """Rebuild schema, load every CSV, then create the views."""
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
    gt = (data_dir / "ground_truth.csv").as_posix()
    con.execute(f"INSERT INTO validation.ground_truth BY NAME SELECT * FROM read_csv('{gt}', header = true)")
    con.execute((SQL_DIR / "views.sql").read_text())
