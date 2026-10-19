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
