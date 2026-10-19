# Scorecard, buckets and downstream effect

Status: ready-for-agent
Blocked by: 04, 05, 06

## What to build

The scorecard module: key matching (fabricated and omitted), field tolerances, the six buckets with silent error rate and catch rate, per-flag precision and recall, per-tier results, and the downstream effect (apply parsed rows as an overlay, rebuild the baseline, compare unit cost, margin, total weekly profit and menu class flips with `sim/matrix.py`) for approve-all and approve-unflagged.

Spec: `../spec.md`.

## Acceptance criteria

- Hand-built tiny cases check each bucket and the downstream numbers.
- A deliberately wrong unflagged row raises the silent error rate and can flip a class; the same row flagged and excluded does not.
- The scorecard works with any client; development and test splits are reported separately.
- `sim/` is not modified.
