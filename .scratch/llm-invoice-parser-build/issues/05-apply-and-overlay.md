# Review step, approved overlay and loader option

Status: ready-for-agent
Blocked by: 02

## What to build

`ingest/apply.py` and `scripts/ingest_apply.py <staging.csv> [--write]`: read decisions, re-validate corrections (`edited` flag), print a summary and diff, write the overlay under `data/approved/` and the append-only `approvals.csv` only with `--write`; idempotent re-application. Add the opt-in `with_approved` merge to `etl/load.py` and `--with-approved` to `etl/run_pipeline.py`.

Spec: `../spec.md`.

## Acceptance criteria

- Default `load_all` and `run_pipeline` results are byte-identical to before; the existing 90 tests, the Node parity check and the export-drift check are unaffected.
- With the flag: overlay cost row replaces the base row for the same ingredient and week; an approved recipe replaces the dish's base rows; new ingredients are appended; a later run beats an earlier one.
- No bulk approval path exists; a blank decision changes nothing; applying the same decisions twice reports "already applied".
- Dry run writes nothing.
