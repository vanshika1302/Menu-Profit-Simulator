"""Run sql/analysis_queries.sql: print each result and save it as a CSV.

    python etl/run_queries.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from etl.warehouse import DB_PATH, SQL_DIR, get_connection  # noqa: E402

OUT_DIR = DB_PATH.parent / "query_results"


def parse_queries(text: str) -> dict[str, str]:
    parts = re.split(r"^-- name:\s*(\w+)\s*$", text, flags=re.M)
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}


def main() -> None:
    queries = parse_queries((SQL_DIR / "analysis_queries.sql").read_text())
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    con = get_connection(read_only=True)
    for name, sql in queries.items():
        df = con.execute(sql).df()
        df.to_csv(OUT_DIR / f"{name}.csv", index=False)
        print(f"\n== {name} ({len(df)} rows)")
        print(df.head(12).to_string(index=False))
    con.close()


if __name__ == "__main__":
    main()
