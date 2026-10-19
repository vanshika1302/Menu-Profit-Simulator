# Spec: LLM invoice and recipe parser (extension of the Menu Profit Simulator)

Produced by the wayfinder map `.scratch/llm-invoice-parser/map.md`. Every decision lives in exactly one map ticket; this spec gathers them so build sessions can start. Where a detail is needed the ticket is named. Vocabulary is in `GLOSSARY.md` (Staged row, Pack size, Catch weight, Approved overlay, Recorded response).

## Problem and reader

The Menu Profit Simulator's cost data is typed in as CSVs. A restaurant has supplier invoices and written recipes, not CSVs. The parser turns invoice and recipe **text** into **staged rows** for the existing `ingredients`, `recipes` and `ingredient_costs` tables, a person approves them, and the unchanged simulator uses them. Reader: the same data science and analytics hiring managers, in a live walkthrough. The takeaway: an LLM does the reading, deterministic code does the arithmetic, a person approves, and the whole thing is scored against known answers, including whether a parsing error would change a menu decision.

## In scope

- Text input only (pasted text or a text export): invoices (core) and recipes (second).
- A Python command-line tool calling Claude through the API behind one interface, with live, recorded and stub implementations.
- Staged rows with flags, reasons and source quotes; a dry-run review step; an opt-in approved overlay.
- A synthetic evaluation set (about 60 documents) with generated truth, a scorecard including downstream effect on contribution margin and menu class, and committed snapshots.
- A demo notebook, a README section, a walkthrough step and a Limitations list.

## Out of scope

PDF and image OCR; any LLM call from the dashboard or the Pages site; live supplier, accounting or POS integrations; auto-approval or bulk approval; fine-tuning; multi-restaurant or multi-currency invoices; chunking long documents; a yield or trim model; density-based weight-to-volume conversion.

## Division of labour (ticket: target mapping and normalisation)

The model reads text and copies raw fields as strings, plus a verbatim source quote. **Code does all unit conversion and cost arithmetic** and checks quantity x price against the line total. The model never converts or computes a cost.

- **Units.** Exact conversions within one dimension: weight (oz, lb, g, kg), volume (fl oz, cup, pint, qt, gal, L), count (each, doz). A small approximate can-size table (`#10` about 108 fl oz) applies only when the ingredient's own unit is a volume. Weight-to-volume and count-to-weight are refused with a flag. An ingredient's own unit stays one of the existing seven (lb, qt, gal, oz, each, doz, head); an input unit that cannot be converted to it is flagged.
- **Pack and catch weight.** Case unit cost = case price / (count x size) in the ingredient's unit (`4/5 LB` at $38 is $1.90 per lb). Catch-weight lines use the billed price per lb on received weight; where both ordered and received are shown, received wins; missing received weight is flagged with no cost.
- **Names.** The prompt carries the ingredient catalogue; the model returns an existing `ingredient_id` or `NEW`; code verifies the id exists; ambiguous is flagged; no fuzzy auto-merge; `NEW` becomes a staged new ingredient with a proposed id and an existing unit.
- **Effective week.** The Monday of the week containing the invoice date; a missing or unreadable date is flagged, never defaulted.
- **Non-ingredient lines.** Fuel surcharges, allowances, prompt-pay discounts, deposits and credits are listed as skipped lines with a category and never costed.
- **Duplicates.** One staged row per ingredient and week; a quantity-weighted average is proposed and flagged as a conflict; a row that would replace an existing one is staged as an "update"; nothing is overwritten silently.
- **Recipes.** The dish must be an existing `item_id`. Code parses fractions, Unicode fractions, mixed numbers and compound amounts. Quantity per serving = total / servings; missing servings is flagged with the row unfilled; a range stages the midpoint with a flag; "to taste" is skipped with a note. The staged quantity is recorded as written; a mention of yield, trim, edible portion or cooked weight adds a "no yield applied" flag.
- **Dropped versus flagged.** No computable cost (missing pack size, unknown unit, weight-to-volume, unknown can size, non-positive price or quantity) gives a flagged row with no value. A disagreeing check (line total beyond max($0.02, 0.5%)) keeps the computed cost with a "check failed" flag and both numbers. Nothing is silently dropped.

## Staging and review (ticket: staging and review workflow)

- **Overlay.** Approved rows go to `data/approved/` with the same three CSV shapes, never to the generator-owned `data/synthetic/`. The loader reads the base then the overlay: a cost row for the same ingredient and week replaces the base row; an approved recipe replaces all base rows for that dish; new ingredients are appended. The merge is **opt-in** (`load_all(..., with_approved=True)`, `--with-approved`), so every committed artifact (`index.html`, notebook, golden fixtures, validation snapshots) is unchanged by approving rows.
- **Staging file.** One CSV per run in an ignored `data/staging/`: `row_id`, `kind` (`ingredient`, `recipe_line`, `cost`), `status` (`proposed`, `flagged`, `skipped`), target fields, `flags`, `reason`, `source_line`, `source_quote`, `decision`, `corrected_value`. Closed flag set: `needs_cost`, `check_failed`, `ambiguous_name`, `new_ingredient`, `conflict`, `update`, `unconvertible_unit`, `missing_date`, `missing_servings`, `range_midpoint`, `no_yield_applied`, `skipped_line`, `edited`.
- **Review.** The reviewer edits `decision` (`approve` or `reject`) and any `corrected_value`, then runs `apply`, which prints a summary and diff and writes nothing unless `--write`. Flagged rows sort first; every row shows its source quote. No bulk approval; blank means no change; corrections are re-validated and get `edited`.
- **Audit and idempotence.** An append-only `data/approved/approvals.csv` records run id, row id, kind, key, decision, time, source hash, original and corrected value. `row_id` is a hash of source file, line and kind, so applying the same decisions twice is a no-op. No in-tool rollback: delete the rows or `git revert`.
- **Version control.** Ignored: `data/staging/`, `data/approved/`. Committed: the synthetic evaluation set and one demo overlay `data/demo_approved/`.

## Model interface and runtime (ticket: model interface and runtime)

- One function `complete_json(system, user, schema) -> dict` behind an interface with **live**, **recorded** and **stub** clients; the parser never imports the SDK.
- Strict structured outputs (`output_config.format`, `strict: true`); default `claude-sonnet-5-5`, overridable by an environment variable; prompt and JSON schema are versioned files; re-check structured-output support on the chosen model at build time.
- Tests and CI use the recorded client. A recording is keyed by a hash of prompt, schema, model and prompt version; a missing one fails loudly. `--live` refreshes recordings and scores the real model; its snapshot is checked by the command, not pytest.
- Code checks after the schema: the ticket-03 checks and **the quoted source line must be found in the document text**. At most one retry, only for semantic failures (quote not found, line total mismatch). The live evaluation reports retry rate and how often a retry helps.
- Injected instructions: the document goes in a delimited data block marked as data only; schema and catalogue checks limit possible output; source quotes show beside each row; adversarial invoices are in the evaluation set; the README says this reduces the risk and does not remove it.
- Output schema: *invoice* (supplier, invoice date as written, lines with description, pack text, ordered and received quantity, unit text, unit and extended price, matched `ingredient_id` or `NEW`, `status` of `ok`/`ambiguous`/`missing`, verbatim `source_quote`; a separate list of fee, credit and deposit lines with a category); *recipe* (dish name, servings, lines with quantity text, unit text, ingredient text, matched id, quote). Every quantity and price is a string as written; code parses it.
- One call per document; a document over about 6,000 tokens is refused with a message to split it. Lowest-variance settings the model documents; the full request is recorded; the live evaluation is repeated three times once to report run-to-run change. Every model failure is an explicit error with no partial staging and no silent stub fallback; a transient API error gets one retry after a short wait.
- Each run writes a sidecar `<run>.meta.json` (model, prompt and schema versions, live or recorded, source hash, call count, retries).
- Key only from `ANTHROPIC_API_KEY`; `--live` required; refuses to run under pytest or CI; prints the number of calls first; default cap 100; `anthropic` lives in a separate optional `requirements-parser.txt`.

## Evaluation set (ticket: evaluation set design)

A seeded `eval/generate_cases.py` renders about 60 documents from the synthetic CSVs with generator-written truth in `data/eval/truth/`: 40 invoices in four tiers (clean; pack notation; hard with catch weight, name variants, fees, credits, deposits, substitutions, typos; adversarial with injection, missing date, unknown units, weight-to-volume traps, ambiguous names), 14 recipes in three tiers, and 6 hand-written adversarial cases labelled by hand. A 70/30 development and test split; the prompt is tuned on development only and the test set is scored once, regenerated with a new seed if the prompt changes afterwards. Messiness types are labelled grounded in the formats research or guessed. Invented supplier names. Committed under `data/eval/`, under 1 MB. A full live run is about 60 to 80 calls.

## Scoring (ticket: metrics and downstream effect)

Rows match on keys (invoice cost rows on ingredient and week, recipe lines on dish and ingredient, skipped lines on line number); unmatched predictions are fabricated, unmatched truth omitted; precision, recall and F1 over rows. Ingredient id and week exact; unit cost and quantity within the larger of 1% or one cent. Every produced row falls into one of six buckets (correct unflagged; correct flagged; wrong flagged; wrong unflagged = **silent error**; omitted; fabricated); the headline numbers are the silent error rate and the catch rate, with per-flag precision and recall. Downstream: apply the parsed rows as an overlay, rebuild the baseline, compare item unit cost and contribution margin, total weekly profit and the number of menu class flips against the baseline from true rows, approving all rows and approving only unflagged rows. A free recorded scorecard `ingest_eval_results.json` is checked by pytest; a live snapshot `ingest_eval_live.json` is checked by the command; development and test reported separately; no pass/fail bounds. The rule-based stub is reported as the baseline in the same scorecard.

## Architecture (ticket: repo architecture)

New package `ingest/` beside the untouched `sim/`: `model_client.py`, `prompts/`, `schemas/`, `units.py`, `normalise.py`, `stage.py`, `apply.py`, plus a scorecard module; the generator in `eval/`; cases in `data/eval/`; tests in `tests/ingest/`. Plain scripts, no Makefile: `scripts/ingest_parse.py <file> --kind invoice|recipe [--live]`, `scripts/ingest_apply.py <staging.csv> [--write]`, `scripts/ingest_eval.py [--live] [--record]`. Only `etl/load.py` and `etl/run_pipeline.py` change (the opt-in overlay). `anthropic` is imported only inside the live client and a test checks that CI never imports it. CI needs no change.

## Presentation (decided during spec assembly)

- **Demo notebook** `notebooks/invoice_parser_demo.ipynb`, executed with outputs, running on recorded responses: parse a synthetic invoice, show the staged rows with flags and source quotes, approve, build the overlay, re-run the baseline with `--with-approved`, and show the cost, margin and menu class change; then the scorecard and the stub baseline. It defines no formulas.
- **README** gains a section "Invoice and recipe parser (extension)" with the pipeline picture, how to run, the scorecard table (live and stub), and the Limitations below.
- **Walkthrough** gains one 60-second step: an invoice with a catch-weight line and a fee, the flagged row, approval, and the class that moves; then the silent error rate.

## Limitations to state in the README

Invoices in the evaluation set are synthetic and rendered by the project's own generator, so real invoices will be messier and scores are not real-world accuracy; the formats research found no real invoice sample and no prevalence data, so "common" and "rare" are judgments; the model can invent or omit quantities and misread units or pack sizes, which is why checks, flags and a person exist; no OCR, PDFs or images; one call per document under a size limit; no yield or trim model (flagged only); no density-based weight-to-volume conversion; the can-size table is approximate; injection defences reduce the risk and do not remove it; confidence is a categorical status and check results, not a probability; results depend on a model version and a prompt version and must be re-recorded when either changes; recorded results are replays; staged rows always need a person; the overlay is opt-in and not part of the committed portfolio artifacts.

## Build order

See `issues/`: numbered slices with blockers. One slice, the live evaluation run, needs a person with an API key.
