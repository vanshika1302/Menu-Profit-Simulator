# Live evaluation run with an API key

Status: done
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

## Comments (run done)

- Run by the agent, with the user's go-ahead, through **Claude Code's headless mode** (`claude -p`, `--tools ""`, no skills, no MCP servers, no settings or project memory, empty temp directory, API keys removed from the environment) on the user's Claude Code subscription, because there was no API key. A new `--backend claude-code` option on `scripts/ingest_eval.py` and `scripts/ingest_parse.py` selects it; `--backend api` stays the default for anyone else. Recordings are keyed `claude-code:claude-sonnet-5-5` and carry `extra: {backend, served_by}`.
- Order: one dev pass (44 documents, 45 calls) -> the prompt was **not changed**; the pass found two bugs in the parser and scorer, fixed before the test run (a received weight written with its unit inside the string; ambiguous lines now accept either reading when flagged `ambiguous_name`); the recorded dev responses replay to F1 1.000 with no silent errors after the fixes -> test set scored once (16 documents, 16 calls: F1 0.990, 0 silent errors, one trap flagged rather than solved) -> the demo invoice recorded (1 call) -> `ingest_eval.py --write` for the replay snapshot (all 60: F1 0.997, 0 silent errors). About 64 calls in all, plus one smoke test and one single-document trial; no API credits used.
- The one miss (`inv_036`, a new-ingredient trap): the model matched `OIL TRUFFLE BLACK` to the catalogue's cooking oil and flagged it ambiguous, instead of proposing a new ingredient. Caught, not silent.
- **Not done:** the three-repeat run-to-run variance check (`--live --split dev --repeats 3`, about 135 calls). It is optional for the README claims, which say it was not measured. If wanted, run it without `--record` so the committed recordings are not overwritten.
- Committed: `data/recordings/` (62 recordings, 668 KB), `ingest_eval_results.json`, `ingest_eval_live.json`, the rebuilt demo notebook, and the README model row.
