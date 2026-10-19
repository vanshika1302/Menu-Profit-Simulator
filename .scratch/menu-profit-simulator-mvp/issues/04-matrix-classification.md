# Menu engineering matrix classification

Status: ready-for-agent
Blocked by: 02, 03

## What to build

Per-category and whole-menu classification as a pure function in `sim/`, with SQL inputs from `sql/views.sql`: dollar CM per unit, trailing 12 weeks, insufficient-data guard (under 50 units), popularity at 70% of equal share (editable), margin at the unit-weighted average, thresholds recomputed under a scenario, class moves, and the class-uncertain flag across bands. Action wording per class.

Spec: `../spec.md`.

## Acceptance criteria

- Matches the matrix rules ticket exactly.
- Classification is invariant to item order.
- Baseline and scenario thresholds are both returned.
