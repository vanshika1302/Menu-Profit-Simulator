# Live evaluation run with an API key

Status: ready-for-human
Blocked by: 08

## What to build

A person with an API key runs the live evaluation: tune the prompt on the development set only, record responses, then score the test set once and commit `ingest_eval_results.json`, `ingest_eval_live.json`, the recordings and the demo-invoice recordings. Run the three-repeat variance check once. Record the model name and prompt version in the snapshot. Check the chosen model still supports strict structured outputs.

Spec: `../spec.md`.

## Acceptance criteria

- Recordings, both snapshots and the variance result are committed; the recorded run reproduces `ingest_eval_results.json` with no key.
- The prompt was not changed after the test set was scored (otherwise a new test seed was generated and noted).
- Cost of the run stayed within the call cap; the real number of calls is noted in the ticket.

## Comments

- Added after slice 10: also record the demo invoice (`python scripts/ingest_parse.py data/demo/invoice_beef_spike.txt --kind invoice --live --record data/recordings`), then re-run `python scripts/build_parser_notebook.py` and fill the model's row in the README scorecard table (see the notes on slices 10 and 11).
- Order that keeps the test set clean: (1) `--live --split dev --record` while tuning the prompt (the prompt and schema are versioned files, so bump the prompt version in `ingest/model_client.py` when the prompt changes); (2) `--live --split test --final --write` once; (3) `--live --split dev --repeats 3` once for the run-to-run change; (4) `python scripts/ingest_eval.py --write` to snapshot the replay; (5) commit the recordings and the three snapshots.
