# Load the warehouse and build the SQL descriptive layer

Status: ready-for-agent
Blocked by: 01

## What to build

`etl/warehouse.py` (one connection function), `etl/load.py`, `etl/run_pipeline.py`, `sql/schema.sql` (raw_* tables and the separate `validation` schema), `sql/views.sql` (item cost, CM, 12-week baseline, popularity share, matrix inputs), `sql/analysis_queries.sql`, `etl/run_queries.py`.

Spec: `../spec.md`.

## Acceptance criteria

- Plain ANSI SQL; `.duckdb` ignored.
- Ground truth lands only in the `validation` schema.
- pytest cross-checks every view against an independent pandas computation on the same CSVs.
