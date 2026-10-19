# Parse pipeline: document to staged rows

Status: done
Blocked by: 02, 03

## What to build

The orchestration behind `scripts/ingest_parse.py <file> --kind invoice|recipe [--live]`: build the prompt with the ingredient catalogue (and menu items for recipes), call the client, validate, run the quote-found check, retry at most once on semantic failure, then use `normalise` for costs and quantities, map names, set the effective week, list skipped lines, detect conflicts and updates against the CSVs, and write the staging file and sidecar.

Spec: `../spec.md`.

## Acceptance criteria

- Every flag in the spec can be produced by a test case; nothing is silently dropped.
- An unknown `ingredient_id` from the model, a quote not found in the source, and a failed line-total check each yield the specified flag.
- A document over the size limit and every model failure produce an explicit error and no partial staging file.
- Works end to end with the stub client and with small hand-written recordings committed as fixtures.

## Comments

- Built (`ingest/parse.py`, `scripts/ingest_parse.py`). Every flag code in the spec is produced by a test; the tier 1 and 2 evaluation invoices recover their true unit costs end to end through an oracle model (the pipeline's arithmetic, not a real model's reading).
- The duplicate-ingredient trap in the evaluation set now has ONE truth row (the weighted average, flagged `conflict`), matching "one staged row per ingredient and week".
- The `update` flag is raised against the catalogue's existing rows. The CLI loads the synthetic data's existing costs, so an invoice dated into one of its 13 weekly cost weeks is staged as an update. The evaluation harness must pass an empty set of existing rows (slice 07/08) or every clean row would be flagged `update`.
- A `NEW` ingredient's staged cost row carries the proposed slug as its `ingredient_id`; the scorecard (slice 07) should treat any row flagged `new_ingredient` as `NEW` when matching against truth.
- Unquantified recipe lines ("to taste") are skipped before any new-ingredient proposal, so they propose nothing.
- Known limitation, to be stated in the README: beverage ingredients whose unit `oz` is a fluid ounce in the data are read as weight by the converter, so volume packs for them are refused and flagged (evaluation case `hw_06`).
