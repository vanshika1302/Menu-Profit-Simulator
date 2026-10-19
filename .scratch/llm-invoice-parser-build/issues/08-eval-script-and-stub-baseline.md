# Evaluation script and the stub baseline snapshot

Status: done
Blocked by: 07

## What to build

`scripts/ingest_eval.py [--live] [--record]`: run the evaluation on stub, recorded or live clients, print the scorecard, write `ingest_eval_results.json` (recorded) and `ingest_eval_live.json` (live, test set), and a committed stub-baseline snapshot checked by pytest. Include the retry-rate report and the three-repeat variance option for live runs.

Spec: `../spec.md`.

## Acceptance criteria

- The stub baseline snapshot is committed and a fast pytest fails on any difference beyond a tight tolerance; no pass/fail bounds on findings.
- Recorded mode never needs a key; live mode honours every guard from the model-client slice.
- The command checks a live snapshot against the committed one and reports a mismatch without failing pytest.
- Running it with no recordings present gives a clear message, not a crash.

## Comments

- Built (`scripts/ingest_eval.py`, `ingest/evaluation.py`, `ingest/baseline_extractor.py`, committed `ingest_eval_stub.json`). Modes: `--stub` (the rule-based baseline), the default (replay recordings from `data/recordings/`), `--live` (with `--record`, `--split dev|test|all`, `--repeats N`). A live run on the test set needs `--final`, and the live snapshot is written only for `--split test --final --write`. Live runs share one call budget across the invoice and recipe clients. With no recordings the command explains how to make them and exits 2.
- The rule-based baseline reads the three supplier layouts and plain recipe lines with regular expressions and matches names to the catalogue by shared words. **It was written knowing the generator's layouts, so it is a favourable baseline**: it scores F1 1.0 on the clean and pack-notation invoices and on every recipe tier, and 0.44 on tier 3 (abbreviated supplier names become flagged new ingredients). Overall F1 is 0.863 with no silent errors. The README must say the cases and the baseline come from the same author, and that the interesting comparison is on the hard tiers and on any real document the rules were not written for.
- Downstream, the baseline's misses (true costs it never applied) leave 19 to 24 items with a margin error (largest $3.97) and 2 to 5 menu class flips, depending on whether every row or only unflagged rows are approved.
- A real bug found while scoring the whole set: two documents can propose the same new ingredient id, which produced a duplicate key in the overlay. The scorecard now de-duplicates and the loader's merge uses `DISTINCT ON`, with a test.
- `by_tier` in the scorecard is keyed by kind and tier (for example `invoice 3`), since invoices and recipes share tier numbers.
