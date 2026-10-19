"""generate (if CSVs are missing) -> load -> create views.

    python etl/run_pipeline.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from etl.generate import generate  # noqa: E402
from etl.load import DATA_DIR, RAW_TABLES, load_all  # noqa: E402
from etl.warehouse import DB_PATH, get_connection  # noqa: E402


def main() -> None:
    if not all((DATA_DIR / f"{n}.csv").exists() for n in RAW_TABLES + ["ground_truth"]):
        print("CSVs missing: generating")
        generate(DATA_DIR)
    con = get_connection()
    load_all(con)
    rows = con.execute(
        "SELECT table_schema, table_name FROM information_schema.tables WHERE table_type = 'BASE TABLE' ORDER BY 1, 2"
    ).fetchall()
    for schema, name in rows:
        n = con.execute(f'SELECT COUNT(*) FROM "{schema}"."{name}"').fetchone()[0]
        print(f"{schema + '.' + name:30s} {n:5d} rows")
    con.close()
    print(f"warehouse: {DB_PATH}")


if __name__ == "__main__":
    main()
