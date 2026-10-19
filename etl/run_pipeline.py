"""generate (if CSVs are missing) -> load -> create views.

    python etl/run_pipeline.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from etl.generate import generate  # noqa: E402
from etl.load import APPROVED_DIR, DATA_DIR, RAW_TABLES, load_all  # noqa: E402
from etl.warehouse import DB_PATH, get_connection  # noqa: E402


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--with-approved", action="store_true",
                    help="merge the person-approved overlay (data/approved/) over the synthetic base; off by default")
    ap.add_argument("--approved-dir", type=Path, default=APPROVED_DIR)
    args = ap.parse_args(argv)
    if not all((DATA_DIR / f"{n}.csv").exists() for n in RAW_TABLES + ["ground_truth"]):
        print("CSVs missing: generating")
        generate(DATA_DIR)
    con = get_connection()
    load_all(con, with_approved=args.with_approved, approved_dir=args.approved_dir)
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
