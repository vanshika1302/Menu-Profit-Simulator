# Where does the parser live in the repo and how does it fit the existing pipeline?

Type: grilling
Status: resolved
Blocked by: 04, 07

## Question

Decide: folder layout and modules, the command-line entry points, how it feeds `etl/` and the warehouse without changing the simulator, the tests and snapshots, dependencies, GLOSSARY additions, and the CI additions. Open seams owned by other tickets: staged row format (04), metrics (06), model interface (07).

## Answer

Settled with the user (all four recommendations accepted).

**Layout.** A new package `ingest/` beside the untouched `sim/`: `model_client.py` (the interface and its live, recorded and stub implementations), `prompts/` and `schemas/` (versioned files), `units.py` (conversion tables and the can-size table), `normalise.py` (code arithmetic and the ticket-03 checks), `stage.py` (the staging CSV and sidecar), `apply.py` (review, dry-run diff and overlay merge). The evaluation generator lives in `eval/`, the cases and truth in `data/eval/`, and tests in `tests/ingest/`.

**Entry points** (plain scripts, matching the repo's style; no Makefile): `scripts/ingest_parse.py <file> --kind invoice|recipe [--live]`, `scripts/ingest_apply.py <staging.csv> [--write]`, `scripts/ingest_eval.py [--live] [--record]`.

**Pipeline contact.** Only `etl/load.py` and `etl/run_pipeline.py` change, to add the opt-in `with_approved` merge from the staging-and-review ticket. `sim/`, the dashboard, the golden fixtures and every committed artifact stay untouched, and default behaviour stays identical.

**Tests and CI.** pytest covers conversions, normalisation, staging, `apply` and the loader (including that the default result is unchanged), using the stub and recorded clients. The `anthropic` package is imported only inside the live client, and a test checks that CI never imports it. The evaluation snapshot is checked by the command, not by pytest. CI needs no changes. Dependencies are as settled in the model-interface ticket: a separate optional `requirements-parser.txt`.

**Glossary.** Terms already added during this effort: Staged row, Pack size, Catch weight, Approved overlay, Recorded response.
