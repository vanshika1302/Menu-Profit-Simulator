# README section, Limitations and walkthrough step

Status: done
Blocked by: 10

## What to build

Add the README section 'Invoice and recipe parser (extension)' with the pipeline picture, run commands, the scorecard table (live and stub) and the Limitations list from the spec; add the 60-second step to `docs/walkthrough.md`; link the demo notebook.

Spec: `../spec.md`.

## Acceptance criteria

- Every limitation in the spec appears; the run commands match the architecture ticket and actually work.
- States plainly that the evaluation invoices are synthetic and rendered by the project's own generator.
- The README tests still pass and a new test checks the new section's commands point at real files.

## Comments

- Built as a draft before slice 09: the README section "Invoice and recipe parser (extension)", the parser Limitations list, a new optional walkthrough step 7 and a link to the demo notebook. A test checks every limitation is present, the commands point at real files, and the baseline row of the scorecard table equals the committed snapshot.
- The model's row in the README scorecard table says "not yet recorded". After slice 09, fill it from `ingest_eval_live.json` (rows F1, silent error rate, the tier 3 F1, class flips) and add the number to walkthrough step 7; then extend `tests/ingest/test_readme_parser.py` to check that row against the live snapshot as it already does for the baseline.
