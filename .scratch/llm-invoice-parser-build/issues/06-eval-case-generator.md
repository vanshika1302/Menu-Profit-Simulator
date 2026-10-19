# Evaluation case generator and committed cases

Status: ready-for-agent
Blocked by: 01

## What to build

`eval/generate_cases.py` (seeded): render about 60 documents from the synthetic CSVs in several supplier-style templates with the four invoice tiers and three recipe tiers, write truth to `data/eval/truth/`, add the 6 hand-written adversarial cases with hand labels, and fix the 70/30 development and test split.

Spec: `../spec.md`.

## Acceptance criteria

- Same seed gives byte-identical files; total size under 1 MB; invented supplier names only.
- Every messiness type is labelled grounded in the formats research or guessed.
- Truth files carry expected cost rows, skipped lines and expected flags for trap cases; truth never appears in a document or prompt.
- Tests check counts per tier, the split, and that rendering then parsing with the pure `units` functions recovers the true unit costs for the clean and pack tiers.
