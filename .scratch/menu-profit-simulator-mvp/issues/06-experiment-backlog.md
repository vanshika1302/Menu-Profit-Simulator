# Experiment backlog generation, scoring and presentation data

Status: ready-for-agent
Blocked by: 05

## What to build

`sim/experiments.py`: candidates from scenario price changes and item class; score = stake x decision uncertainty x feasibility / normalised risk cost; one-day blocks, whole weeks, m = 1, 12-week cap, n = 32 sigma^2/Delta^2; two lists (feasible now, needs pooling); guardrails and stop rules; full entry fields.

Spec: `../spec.md`.

## Acceptance criteria

- Risk cost normalised by item weekly profit (see the amendment comment on the backlog ticket).
- Weak-evidence candidates get defensible stake and feasibility inputs documented in the code, not placeholders.
- Tests: scores monotonic in stake and feasibility; decision uncertainty is 0 when eps* is outside the band and 1 when it splits the band evenly.
