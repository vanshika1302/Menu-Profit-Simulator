# Executed demo notebook

Status: done
Blocked by: 09

## What to build

`notebooks/invoice_parser_demo.ipynb` on recorded responses: parse a synthetic invoice with a catch-weight line and a fee, show staged rows with flags and source quotes, approve, build the overlay and a small `data/demo_approved/`, re-run the baseline with `--with-approved`, show the cost, margin and class change, then the scorecard against the stub baseline. Built by a script like `scripts/build_notebook.py`.

Spec: `../spec.md`.

## Acceptance criteria

- Runs top to bottom from a clean checkout with no key; defines no formulas; fully executed with outputs committed.
- A test checks it is executed, error-free and that no cell imports `anthropic`.
- The committed portfolio artifacts (`index.html`, the main notebook, golden fixtures) are unchanged.

## Comments

- Built before slice 09, as a drafted version that falls back to the rule-based baseline when the model has no recording for the demo invoice, and says which one it used. It needs no key either way. After the live run, re-run `python scripts/build_parser_notebook.py` so the notebook shows the model reading the invoice and the model's scorecard (it picks up `ingest_eval_live.json` automatically).
- The demo invoice is `data/demo/invoice_beef_spike.txt` (constructed: beef up about 30%). Slice 09 must record it: `python scripts/ingest_parse.py data/demo/invoice_beef_spike.txt --kind invoice --live --record data/recordings`.
- The committed demo overlay is `data/demo_approved/` (regenerated with a fixed approval time so the files are stable). With it, Short Rib moves from Puzzle to Dog, and two untouched burgers (Philly Cheesesteak and Veggie Burger) move from Dog to Puzzle because their category's thresholds shift; the notebook reports all three.
