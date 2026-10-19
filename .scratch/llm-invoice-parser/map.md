# Map: LLM invoice and recipe parser

Label: wayfinder:map

## Destination

A **build-ready spec** (PRD plus ordered implementation slices) for the LLM invoice and recipe parser that extends the finished Menu Profit Simulator, executed later by separate AFK sessions. Done when nothing is left to decide before someone goes and builds it. This effort plans; it does not build.

## Notes

- Domain: turning supplier invoices and written recipes into the simulator's existing cost data. A fresh effort: the MVP (`../menu-profit-simulator/map.md`, spec in `../menu-profit-simulator-mvp/spec.md`) is finished and live, and listed this parser as out of scope with one obligation: keep the recipe and ingredient-cost schema narrow and stable so a parser can target it.
- Target schema (already fixed, do not redesign): `ingredients(ingredient_id, name, unit)`, `recipes(item_id, ingredient_id, qty_per_serving)`, `ingredient_costs(ingredient_id, effective_week, unit_cost)`. Units in the data today: lb, qt, gal, oz, each, doz, head. The simulator reads only the latest unit cost times recipe quantity; there is no waste or yield model.
- Reader: same as the MVP, data science / analytics hiring managers in a live walkthrough. The parser shows up in the notebook, the README and one walkthrough step. The dashboard stays static and never calls an LLM.
- Constraints: Python command-line tool calling Claude through the API; the key comes from an environment variable and never enters the repo; the model sits behind one function so the evaluation can run against a recorded or stub model; CI never calls a real model. Output goes to a **staged row** file with flags and reasons on anything uncertain, and a person approves before any CSV changes. Text input only (pasted text or a text export): no PDF or image OCR. Invoices are the core, recipes second.
- Evaluation: the data is synthetic, so the answer is known. Generate invoices and recipes from the existing CSVs with controlled messiness, add a few hand-written hard cases, and score field accuracy, unit-conversion correctness and the downstream effect (does a parsing error change an item's contribution margin or flip its menu engineering class?). As in the MVP, prefer committed result snapshots to pass/fail bounds on findings.
- Style: the MVP's conventions (local-markdown tracker, `GLOSSARY.md`, results framed as method behaviour on synthetic data, limitations stated plainly).
- Tracker: local markdown. Tickets in `issues/`.

## Decisions so far

- Destination, reader, scope, runtime, review step and evaluation approach were settled in the charting grill (no ticket): spec as the endpoint; same reader; both invoices and recipes as text; Python tool calling Claude with a stub-able model function; staged rows with human approval; synthetic eval set with downstream CM scoring.
- [What do real supplier invoices and written recipes look like?](issues/01-invoice-and-recipe-formats.md): pack notation (`6/#10`, `4/5 LB`), catch weight billed on received lb, case-vs-unit prices, fee and credit lines to exclude, inconsistent names, compound recipe quantities and AP/EP yield; no real invoice sample or distributor docs found, so prevalence is judgment, and a suggested scope is recorded.
- [What does the evidence say about LLM extraction from semi-structured documents, and how should it be evaluated?](issues/02-llm-extraction-practice.md): strict structured outputs guarantee shape only, so quantities, units and omissions need code checks (line total, evidence quote found in source); no usable model confidence, so flag from check failures and a categorical ok/ambiguous/missing status; prompt injection is real but the tool has no tools and a human approver; no published standard for normalised or downstream scoring, so that method is this project's own; misread rates are unverified and must be measured.

## Not yet specified

- **Presentation:** how the parser appears in the notebook, README and walkthrough, and what the Limitations section must say (hallucinated quantities, unit and pack-size errors, no OCR).
- **Untrusted input:** an invoice is text from outside; whether and how the tool defends against instructions hidden in it, and what a staged row may never do.
- **Cost, latency and batching** of model calls, once the extraction approach is chosen.
- **Spec assembly:** the PRD and ordered slices, once the decisions above land.

## Out of scope

- **PDF and image OCR, scanned invoices.** Text input only.
- **Any LLM call from the dashboard or GitHub Pages page.** The dashboard stays static.
- **Live supplier, accounting or POS integrations.**
- **Auto-approval of staged rows.** A person always approves.
- **Fine-tuning or training a model.**
- **Multi-restaurant or multi-currency invoices.**
