# Review step, approved overlay and loader option

Status: done
Blocked by: 02

## What to build

`ingest/apply.py` and `scripts/ingest_apply.py <staging.csv> [--write]`: read decisions, re-validate corrections (`edited` flag), print a summary and diff, write the overlay under `data/approved/` and the append-only `approvals.csv` only with `--write`; idempotent re-application. Add the opt-in `with_approved` merge to `etl/load.py` and `--with-approved` to `etl/run_pipeline.py`.

Spec: `../spec.md`.

## Acceptance criteria

- Default `load_all` and `run_pipeline` results are byte-identical to before; the existing 90 tests, the Node parity check and the export-drift check are unaffected.
- With the flag: overlay cost row replaces the base row for the same ingredient and week; an approved recipe replaces the dish's base rows; new ingredients are appended; a later run beats an earlier one.
- No bulk approval path exists; a blank decision changes nothing; applying the same decisions twice reports "already applied".
- Dry run writes nothing.

## Comments

- Built (`ingest/apply.py`, `scripts/ingest_apply.py`, `etl/load.py`, `etl/run_pipeline.py`). Default `load_all` and `run_pipeline` results are unchanged (tested by comparing every raw table with an overlay present but not requested); the existing tests, the parity check and the export-drift check are unaffected.
- `corrected_value` is a bare number (the row's value: cost for a cost row, quantity for a recipe line, unit for a new ingredient) or `field=value` pairs separated by `;` (allowed fields: `unit_cost`, `qty_per_serving`, `ingredient_id`, `effective_week`, `unit`, `name`). Corrections are re-checked (ingredient exists, numbers positive, week is a Monday, unit is one of the seven) and the approval log records the original value, the correction and an `edited` flag.
- An approved recipe replaces every earlier row for its dish; the dry run says how many lines it replaces (for example "approving 1 line(s) for wings replaces all 3 existing recipe line(s)"), because approving only part of a recipe silently shortens it.
- A new ingredient whose id already exists keeps the base row. A new ingredient approved in the same file is a valid target for the file's cost and recipe rows.
