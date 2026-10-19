# Validation scorecard, leakage tests, result snapshots

Status: ready-for-agent
Blocked by: 05, 06

## What to build

`sim/validation.py` (the only reader of ground truth), `scripts/run_validation.py` writing `validation_results.json`, runtime leakage tests, snapshot test.

Spec: `../spec.md`.

## Acceptance criteria

- Scorecard: band hit rate, profit-range coverage over a standard scenario set, verdict accuracy (including wrong 'pays off under all bands'), naive before/after history error.
- Leakage: import check; outputs identical with `ground_truth.csv` removed or garbage.
- Committed `validation_results.json`; a fast pytest recomputes and fails on any difference beyond a tight tolerance.
- No pass/fail bounds on the findings.
