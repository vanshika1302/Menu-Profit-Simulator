# Golden fixtures, JS port and parity test

Status: done
Blocked by: 05, 06

## What to build

`scripts/make_golden.py` (a few dozen scenarios: no change, price rise, price cut, category-wide, beef shock, combined, substitution at 0/25/100%, each band, per-category overrides, insufficient-data item, a change at the break-even), `dashboard/sim.js` (model, classification, scoring), `tests/parity.mjs`.

Spec: `../spec.md`.

## Acceptance criteria

- Relative 1e-9 on numbers; exact on classes and ranks.
- Fixtures cover outputs, classes and the ranked backlog.
- Node is a dev-only dependency.
