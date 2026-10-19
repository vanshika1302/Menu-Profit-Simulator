# Staging file, flag vocabulary and sidecar

Status: done
Blocked by: 01

## What to build

`ingest/stage.py`: the staging CSV (columns and closed flag set from the spec), skipped-line rows, content-hash `row_id`, the `<run>.meta.json` sidecar, and reading a reviewed staging file back.

Spec: `../spec.md`.

## Acceptance criteria

- Columns, statuses and the 13 flag codes exactly as in the spec; flagged rows sort first.
- `row_id` is stable across re-parses of the same file; sidecar fields as in the spec.
- Round-trip test: write, edit `decision` and `corrected_value`, read back.
- `data/staging/` and `data/approved/` added to `.gitignore`.
