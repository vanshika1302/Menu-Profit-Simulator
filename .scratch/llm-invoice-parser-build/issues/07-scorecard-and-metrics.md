# Scorecard, buckets and downstream effect

Status: done
Blocked by: 04, 05, 06

## What to build

The scorecard module: key matching (fabricated and omitted), field tolerances, the six buckets with silent error rate and catch rate, per-flag precision and recall, per-tier results, and the downstream effect (apply parsed rows as an overlay, rebuild the baseline, compare unit cost, margin, total weekly profit and menu class flips with `sim/matrix.py`) for approve-all and approve-unflagged.

Spec: `../spec.md`.

## Acceptance criteria

- Hand-built tiny cases check each bucket and the downstream numbers.
- A deliberately wrong unflagged row raises the silent error rate and can flip a class; the same row flagged and excluded does not.
- The scorecard works with any client; development and test splits are reported separately.
- `sim/` is not modified.

## Comments

- Built (`ingest/scorecard.py`). Rows match on keys; six buckets (clean hit, correct but flagged, wrong flagged, silent error, fabricated, omitted) with the silent error rate (silent wrong rows plus unflagged fabricated rows, over rows produced) and the catch rate (wrong rows that carried a flag); per-flag, skipped-line and new-ingredient precision and recall; per tier, kind and split. Tolerance: the larger of 1% or one cent (0.001 for quantities).
- A parsed `new_ingredient` cost row is matched against the truth row `NEW`. The `update`, `skipped_line` and `edited` flags are ignored when scoring flags (context-dependent or added later by a person). Evaluation runs must parse with an empty set of existing rows (`load_catalogue(..., with_existing=False)`).
- The downstream effect places every parsed cost in the latest cost week of the synthetic data, so each invoice is treated as the current cost evidence (otherwise mid-year invoices would not move the baseline). It compares, for approve-all and approve-unflagged, items with a margin error, mean and maximum margin error, weekly profit error and menu class flips against the baseline built from the true rows. A wrong cost on one item can flip a neighbour's class because the category thresholds move.
- A generator bug found while testing against the committed truth: a tier-4 invoice's random ordinary lines could use the same ingredient as its trap line, giving two truth rows one key. The ordinary lines now exclude the trap ingredients (20 evaluation files regenerated) and a test checks that no case has duplicate truth keys.
