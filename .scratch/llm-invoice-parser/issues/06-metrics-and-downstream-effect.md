# How is the parser scored, including the effect on the simulator's answers?

Type: grilling
Status: resolved
Blocked by: 05

## Question

Decide: field-level accuracy, unit-conversion correctness, handling of refusals and flags (a flagged wrong row is better than a silent wrong one); the downstream metric (error in an item's unit cost and contribution margin, and whether a menu engineering class flips); how results are snapshotted and shown without pass/fail bounds, as in the MVP validation strategy; and how a stub or recorded model keeps the scoring deterministic and free in CI.

## Answer

Settled with the user (all six recommendations accepted).

**Row matching.** Match on keys: invoice cost rows on (ingredient, week), recipe lines on (dish, ingredient), skipped lines on their line number. A predicted row with no truth row is **fabricated**; a truth row with no prediction is **omitted**. Precision, recall and F1 are computed over rows (the line-item scoring precedent from the extraction research).

**Field correctness.** Ingredient id and week must match exactly. Unit cost and quantity per serving must be within the larger of 1% or one cent. Results are reported per difficulty tier and overall, separately for cost rows, recipe lines, new ingredients, skipped-line categories and flags.

**Flags versus silent errors.** Every produced row falls into one of six buckets: correct and unflagged; correct but flagged (over-cautious); wrong but flagged (error caught); wrong and unflagged (**silent error**); omitted; fabricated. The headline numbers are the **silent error rate** (wrong, unflagged rows over rows produced) and the **catch rate** (wrong rows that carry a flag). Trap cases name the flag they should raise, and each flag code gets its own precision and recall.

**Downstream effect** (this project's own method; no published standard exists). Apply the parsed rows as an overlay on the synthetic data, rebuild the baseline, and compare with the baseline built from the true rows: each item's unit cost and contribution margin, total weekly profit, and how many items change menu engineering class (using `sim/matrix.py`). Run twice: approving every row (the worst case) and approving only unflagged rows (what a hurried reviewer does).

**Snapshots, no bounds.** A committed scorecard for the recorded run, `ingest_eval_results.json`, is deterministic and free, so pytest checks it and fails on any change. A separate committed snapshot for the live model, `ingest_eval_live.json`, is checked only by the command. Development and test sets are reported separately, and the live snapshot covers the test set. No findings get pass/fail bounds, as in the MVP validation strategy.

**Baseline and framing.** The rule-based stub client doubles as the baseline and appears in the same scorecard, so a reader can see whether the LLM beats a simple rule. The README states the framing: the cases are synthetic and rendered by the project's own generator, so real invoices will be messier and these scores are not real-world accuracy.

Carried forward: the scorecard module and snapshot checks placed under `ingest/` and `tests/ingest/` (architecture ticket); the presentation of these results in the notebook, README and walkthrough (spec assembly).
