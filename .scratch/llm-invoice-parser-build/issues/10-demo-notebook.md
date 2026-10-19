# Executed demo notebook

Status: ready-for-agent
Blocked by: 09

## What to build

`notebooks/invoice_parser_demo.ipynb` on recorded responses: parse a synthetic invoice with a catch-weight line and a fee, show staged rows with flags and source quotes, approve, build the overlay and a small `data/demo_approved/`, re-run the baseline with `--with-approved`, show the cost, margin and class change, then the scorecard against the stub baseline. Built by a script like `scripts/build_notebook.py`.

Spec: `../spec.md`.

## Acceptance criteria

- Runs top to bottom from a clean checkout with no key; defines no formulas; fully executed with outputs committed.
- A test checks it is executed, error-free and that no cell imports `anthropic`.
- The committed portfolio artifacts (`index.html`, the main notebook, golden fixtures) are unchanged.
