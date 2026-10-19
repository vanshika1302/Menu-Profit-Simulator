# Spec: Menu Profitability Simulator (MVP)

Produced by the wayfinder map `.scratch/menu-profit-simulator/map.md`. Every decision below lives in exactly one map ticket; this spec gathers them so a build session can start. Where a detail is needed, the ticket is named so you can open it. Vocabulary is in `GLOSSARY.md`.

## Problem and reader

How can a restaurant identify which menu items and operational changes will improve profit without hurting customer demand? This is a portfolio project for data science and analytics hiring managers, likely walked through live. The takeaway: elasticity is treated as an assumption, uncertainty is quantified, and the result is a testable experiment plan. Favour visible assumptions over feature count.

## In scope (MVP)

1. Item contribution margin and the menu engineering matrix (Star, Plowhorse, Puzzle, Dog).
2. Ingredient-cost shock simulator (e.g. beef +20%).
3. Price scenarios under low / medium / high elasticity bands.
4. Break-even volume drop per price change.
5. Substitution slider.
6. Ranked experiment backlog with guardrail metrics and stop rules.

Priority if cutting: features 1-4 are the core; cut substitution polish before the experiment backlog.

## Out of scope

LLM invoice/recipe parser (feature 7; the recipe and ingredient-cost schema stays narrow and stable for it), real or downloaded datasets, multi-location, live POS integration, ingesting experiment results to update the model automatically (manual per-item elasticity override only).

## Data (ticket: Synthetic restaurant design and hidden ground truth)

- Casual full-service American bistro, 30 items in 6 categories (names and base prices in the ticket); seven items contain beef.
- Five small CSVs in `data/synthetic/`: `menu_items`, `ingredients`, `recipes`, `ingredient_costs` (a history), `weekly_sales` (week_start, item_id, units_sold, avg_selling_price). 52 weeks x 30 items. Seed 42, one command rebuilds. Total under ~500 KB.
- Price history is modest and noisy: 4-5 items get a 5-8% rise mid-year plus two short promos, confounded with seasonality, so history gives only a hint about elasticity.
- Hidden ground truth in a separate validation-only `ground_truth.csv` (authored, not empirical): category elasticities about -0.4 (drinks and sides) to -1.4 (entrees) with jitter; 30-50% within-category substitution. Never read by the simulator or dashboard.
- Volumes and costs are tuned so all four classes are populated. Note: the 70%-of-equal-share rule is lenient, so class balance depends on how concentrated sales are; the generator must be tuned with that in mind.

## Simulation model (ticket: Simulation model)

- Constant-elasticity demand: units = baseline x (new price / old price)^elasticity, intended within about +/-15% price change.
- Global bands: low -0.5, medium -1.0, high -1.8 (from the elasticity benchmarks research; not centred on the ground truth, so some items genuinely miss). Optional per-item/category override in the dashboard.
- Cost shock: percentage change to ingredient unit cost flows through recipes to item cost; separate lever from price; optional pass-through lever. No waste or yield.
- Baseline: trailing 12 weeks, latest prices and costs. Outputs in weekly contribution profit and annualized.
- Substitution: slider (0-100%, default 25%, labelled an assumption) of lost buyers who switch, same category, in proportion to baseline popularity. Single-pass. Price cuts mirror it as cannibalization.
- Uncertainty: profit change as a low-to-high range across bands, plus break-even elasticity eps* = ln((P0-c)/(P1-c)) / ln(P1/P0) and a plain verdict per item ("pays off under all bands", "pays off only if demand is less/more elastic than X", "loses money under all bands"). No probability of payoff.
- Break-even volume drop: shown both ways: dP / (CM + dP), and net of substitution dP / (CM + dP - s x CM_dest).
- Outputs per scenario: units, revenue, ingredient cost, contribution profit, change vs baseline, CM per unit, food-cost %; per price change the break-even drop, predicted drop per band, break-even elasticity and verdict.

## Menu engineering matrix (ticket: Menu engineering matrix rules)

Per category by default with a whole-menu toggle; CM in dollars per unit; trailing 12 weeks; under 50 units = insufficient data; popular if share >= 70% of an equal share (editable); high margin if at or above the unit-weighted average CM; thresholds recomputed under a scenario and class moves shown with both sets of thresholds; headline class uses the medium band with a "class uncertain" flag when low or high band differs; action wording per class (in the ticket).

## Experiment backlog (ticket: Experiment backlog ranking, guardrails and stop rules, plus its amendment comment)

- Three types: switchback price test, menu-design test, portion test, each labelled by evidence strength (price: method-backed; others: weak priors; no effect sizes quoted from the weak studies).
- Candidates from scenario price changes and the item's class (default mapping in the ticket).
- Score = stake x decision uncertainty x feasibility / risk cost, with risk cost **normalised** by item weekly profit. Decision uncertainty = 4p(1-p), p = share of the band on the losing side of eps*.
- Duration: one-day blocks, whole weeks, carryover m = 1 (assumed), sigma from synthetic data, n = 32 sigma^2 / Delta^2 per arm, 12-week cap.
- Two lists: "Feasible now" and "Needs pooling or a larger effect", each ranked by the score.
- Guardrails (policy defaults): total units (traffic proxy), menu-total contribution profit, same-category units; stop-worthy at units down 3% or profit down 2%.
- Stop rules: harm stop after two consecutive weekly breaches (after one full week of each arm), cap stop, no early success stop, conclusion read at the planned end with a randomization test.
- Each entry: rank and factors, target, type, evidence label, hypothesis in project terms, design, duration and flag, primary metric and MDE, guardrails, stop rules, decision rule, the assumptions it depends on.
- Scoring is also ported to JS so the dashboard re-ranks live.

## Architecture (ticket: Repo and pipeline architecture)

Python `sim/` (pure functions) is the reference model; a JS port in `dashboard/sim.js` drives the sliders; golden fixtures and a Node parity test keep them equal. SQL (DuckDB, plain ANSI) holds the descriptive layer; ground truth loads into a separate `validation` schema read only by `sim/validation.py`. One self-contained root `index.html` with data inlined, rendered from `dashboard/template.html`, served by GitHub Pages from `main`. Layout, run order and dependencies are in the ticket (`etl/`, `sql/`, `sim/`, `notebooks/`, `scripts/`, `tests/`, `requirements.txt`).

## Dashboard (ticket: Dashboard UX prototype)

Hybrid: story frame (problem, "synthetic data", "elasticity is an assumption") -> sticky hatched assumption banner (editable bands and substitution) -> cockpit grid (levers left; matrix above the items view centre; profit tiles, class changes and backlog right). Items view: sortable rows with class (baseline -> scenario), price and CM, break-even drawn against the hatched assumed band, verdict, low-to-high profit bar, and an item drawer. Visual rules: hatching = depends on the assumed elasticity; anything not hatched does not; dashed ring = class uncertain; dashed tail = class moved; class = colour plus marker shape; dark mode; stacked on narrow screens; validation aggregates and limitations below the tool. The prototype on branch `prototype/dashboard-ux` (local, throwaway) is reference only; rewrite it properly.

## Validation (ticket: Validation strategy)

Identity-based formula tests; generator and SQL-vs-pandas tests (all four classes appear); runtime leakage tests (simulator and export unchanged with `ground_truth.csv` removed; `index.html` scanned for ground-truth values); wide golden-fixture parity at 1e-9; ground-truth scorecard (band hit rate, profit-range coverage, verdict accuracy, naive-history error); a modest Monte Carlo recovery check (top five backlog entries, 200 replications); no pass/fail bounds on findings but committed result snapshots; GitHub Actions runs pytest, the Node parity check and an export-drift check.

## README outline (mirrors the Airbnb project)

Live link; Business problem; Data (synthetic, authored truth, why); Architecture diagram; Tech stack; Repository structure; How to run (the commands in the architecture ticket); Key findings (from the notebook); Validation (scorecard table, framed as: synthetic data and authored truth, so this shows the method works and where it fails, not real-world accuracy; misses are shown); Limitations.

## Limitations to state in the README

Synthetic data and authored ground truth; elasticity assumed (bands from published ranges, thin item-level evidence, some research figures unverified: see the experiment-design and elasticity research tickets); global bands miss about five items by design; price range about +/-15%; single-pass substitution and no other cross-price effects; no waste or yield modelling; non-seasonal baseline; matrix groups of 4-7 items are noisy and the 70% rule is lenient; total units as a traffic proxy (no covers, satisfaction, waste or staff load); assumed carryover m = 1 and sigma from synthetic data; guardrail thresholds are policy choices; menu-design and portion evidence is weak (and one widely cited label study has an integrity problem); no sequential stopping boundaries claimed; results are not ingested back into the model.

## Build order

See `issues/` in this folder: numbered slices with blockers. Slices run as separate sessions; the last one that needs a person is enabling GitHub Pages in the repo settings.
