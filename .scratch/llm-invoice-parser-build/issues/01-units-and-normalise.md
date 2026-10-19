# Units, quantity parsing and cost arithmetic

Status: ready-for-agent
Blocked by: 

## What to build

`ingest/units.py` and `ingest/normalise.py`: exact conversions within weight, volume and count, the approximate can-size table (volume ingredients only), parsing of fractions, Unicode fractions, mixed numbers, compound amounts (`3 lb 6 oz`), pack text (`4/5 LB`, `6/#10`), price strings (`$1,234.50`), case, catch-weight and each-price arithmetic into the ingredient's own unit, and the line-total check (max($0.02, 0.5%)). Pure functions, no model, no file access.

Spec: `../spec.md`.

## Acceptance criteria

- Every rule in the spec's division-of-labour section is a tested function; weight-to-volume and count-to-weight are refused with a reason.
- Hand-computed cases (e.g. `4/5 LB` at $38 is $1.90 per lb; `#10` can only for volume ingredients; `93/8` is not silently parsed as 9 3/8).
- No-computable-cost cases return a structured refusal, never a guess.
- pytest in `tests/ingest/`; the existing 90 tests still pass.
