"""One place to open the DuckDB warehouse."""
from __future__ import annotations

from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "processed" / "menu_warehouse.duckdb"
SQL_DIR = ROOT / "sql"


def get_connection(path: Path | str | None = DB_PATH, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open the warehouse. Pass ':memory:' (or None) for an in-memory database."""
    if path is None or str(path) == ":memory:":
        return duckdb.connect(":memory:")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path), read_only=read_only)
