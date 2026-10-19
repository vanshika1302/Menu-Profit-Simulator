# Evaluation script and the stub baseline snapshot

Status: ready-for-agent
Blocked by: 07

## What to build

`scripts/ingest_eval.py [--live] [--record]`: run the evaluation on stub, recorded or live clients, print the scorecard, write `ingest_eval_results.json` (recorded) and `ingest_eval_live.json` (live, test set), and a committed stub-baseline snapshot checked by pytest. Include the retry-rate report and the three-repeat variance option for live runs.

Spec: `../spec.md`.

## Acceptance criteria

- The stub baseline snapshot is committed and a fast pytest fails on any difference beyond a tight tolerance; no pass/fail bounds on findings.
- Recorded mode never needs a key; live mode honours every guard from the model-client slice.
- The command checks a live snapshot against the committed one and reports a mismatch without failing pytest.
- Running it with no recordings present gives a clear message, not a crash.
