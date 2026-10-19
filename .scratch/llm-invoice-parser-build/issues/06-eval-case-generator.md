# Evaluation case generator and committed cases

Status: done
Blocked by: 01

## What to build

`eval/generate_cases.py` (seeded): render about 60 documents from the synthetic CSVs in several supplier-style templates with the four invoice tiers and three recipe tiers, write truth to `data/eval/truth/`, add the 6 hand-written adversarial cases with hand labels, and fix the 70/30 development and test split.

Spec: `../spec.md`.

## Acceptance criteria

- Same seed gives byte-identical files; total size under 1 MB; invented supplier names only.
- Every messiness type is labelled grounded in the formats research or guessed.
- Truth files carry expected cost rows, skipped lines and expected flags for trap cases; truth never appears in a document or prompt.
- Tests check counts per tier, the split, and that rendering then parsing with the pure `units` functions recovers the true unit costs for the clean and pack tiers.

## Comments

- Built. 60 documents (44 invoices counting 4 hand-written, 16 recipes counting 2 hand-written), about 490 KB, split 44 development and 16 test. Truth is derived from the rendered text (case price in cents divided by pack quantity, computed with Fractions in the generator), so a correct reader recovers it exactly; it stays within rounding of the synthetic data's own costs.
- Beverage ingredients (`draft_beer`, `house_wine`) are left out of the generated invoices: their unit `oz` is a fluid ounce in the data, but the converter reads `oz` as weight. They appear only in hand-written case `hw_06`, labelled as a known limitation (volume packs are refused and flagged). Slice 04 should state this limitation in the README, or add a per-ingredient dimension override if it is judged worth the complexity.
- Each truth row carries `raw` fields (description, pack text, quantity, unit, prices) so a test can confirm the rendered line contains them and the pure unit functions recover the truth.
