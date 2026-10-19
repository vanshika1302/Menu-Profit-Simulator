# Parse pipeline: document to staged rows

Status: ready-for-agent
Blocked by: 02, 03

## What to build

The orchestration behind `scripts/ingest_parse.py <file> --kind invoice|recipe [--live]`: build the prompt with the ingredient catalogue (and menu items for recipes), call the client, validate, run the quote-found check, retry at most once on semantic failure, then use `normalise` for costs and quantities, map names, set the effective week, list skipped lines, detect conflicts and updates against the CSVs, and write the staging file and sidecar.

Spec: `../spec.md`.

## Acceptance criteria

- Every flag in the spec can be produced by a test case; nothing is silently dropped.
- An unknown `ingredient_id` from the model, a quote not found in the source, and a failed line-total check each yield the specified flag.
- A document over the size limit and every model failure produce an explicit error and no partial staging file.
- Works end to end with the stub client and with small hand-written recordings committed as fixtures.
