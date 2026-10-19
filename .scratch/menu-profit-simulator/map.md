# Map: Menu Profitability Simulator

Label: wayfinder:map

## Destination

**Reached.** A **build-ready spec** (PRD plus a sequenced list of implementation slices) for the Menu Profitability Simulator MVP, which later AFK sessions execute. Done when nothing is left to decide before someone goes and builds it. This effort plans; it does not build.

## Notes

- Domain: restaurant menu profitability. Problem: which menu items and operational changes improve profit without hurting demand?
- Reader: data science / analytics hiring managers, with a live walkthrough in mind. The takeaway: elasticity is treated as an assumption, uncertainty is quantified, and it becomes a testable experiment plan. Favour visible assumptions and a story-telling README over feature count.
- MVP core (priority order): (1) item contribution margin + menu engineering matrix, (2) ingredient-cost shock, (3) price scenarios with low/medium/high elasticity bands, (4) break-even volume threshold per price change, (5) substitution slider, (6) ranked experiment backlog with guardrail metrics and stop rules. If cutting, cut substitution polish before the experiment backlog.
- Constraints: no large datasets; small generated synthetic restaurant (~30 items, recipes, ingredient costs, 12 months of weekly sales) saved as small CSVs. Stack: Python, DuckDB, SQL, a notebook, static dashboard on GitHub Pages.
- Style reference: `~/Downloads/Airbnb-Smart-Price-Optimizer` (github.com/vanshika1302/Airbnb-Smart-Price-Optimizer): `etl/` Python modules -> DuckDB warehouse -> `sql/` + notebook; single-page `index.html` case study with a live tool; README with Business problem / Data / Architecture / Limitations.
- Glossary lives at `GLOSSARY.md` (per user's global config). Use its vocabulary.
- Tracker: local markdown. Tickets in `issues/`.

## Decisions so far

- [Restaurant experiment design practice](issues/05-restaurant-experiment-design-research.md): switchback precision depends on time blocks not covers; menu/portion evidence is weak; small lifts at one restaurant need ~30 weeks, so feasibility must feature in ranking; guardrail thresholds are policy choices. Some claims unverified (see ticket).
- [Elasticity benchmarks for restaurant menu items](issues/04-elasticity-benchmarks-research.md): pooled FAFH about -0.81 (range -0.23 to -1.76) but strongly service-level dependent (limited-service about -0.13 to -0.7, full-service about -1.0 to -1.96); item-level and within-menu substitution evidence is thin, so substitution stays a user assumption. Bands not yet decided.
- [Synthetic restaurant design and hidden ground truth](issues/01-synthetic-restaurant-design.md): casual American bistro, 30 items in 6 categories (7 with beef); five-file CSV schema with weekly price; modest noisy price history; hidden authored ground truth (elasticity by category about -0.4 to -1.4, within-category substitution) in a validation-only file; seed 42, committed under `data/synthetic/`.
- [Simulation model: elasticity, cost shock, substitution, uncertainty](issues/03-simulation-model.md): constant-elasticity demand within about +/-15%; global bands -0.5/-1.0/-1.8 (not centred on the ground truth); cost shock and price are composable levers; trailing-12-week baseline; same-category substitution by popularity (25% default); uncertainty shown as a band range plus break-even elasticity and verdict, no probability; break-even drop shown with and without substitution.
- [Repo and pipeline architecture](issues/06-repo-and-pipeline-architecture.md): Python `sim/` is the reference model with a JS port and golden-fixture parity tests; SQL holds the descriptive layer, ground truth in a separate `validation` schema read only by `sim/validation.py`; one inlined root `index.html` on GitHub Pages; folder layout, run order, pytest and `requirements.txt` fixed.
- [Experiment backlog ranking, guardrails and stop rules](issues/08-experiment-backlog-ranking.md): three experiment types with evidence-strength labels, candidates from item class and scenario; score = stake x decision uncertainty x feasibility / risk cost (uncertainty = whether break-even elasticity sits inside the band); one-day blocks, whole weeks, 12-week cap, m = 1; guardrails on total units and profit (policy defaults); harm/cap stops, no early success stop; live re-ranking via a JS port of the scoring.
- [Menu engineering matrix rules](issues/02-menu-engineering-matrix-rules.md): classified per category by default (whole-menu toggle), CM in dollars per unit, trailing 12 weeks, under 50 units = insufficient data; popular = share >= 70% of equal share, high margin = at or above unit-weighted average CM; thresholds recomputed under a scenario with class moves shown; headline class uses the medium band with a "class uncertain" badge; action wording per class matches the backlog mapping.
- [Validation strategy](issues/09-validation-strategy.md): identity-based formula tests, data/SQL cross-checks, runtime leakage tests, wide golden-fixture parity (1e-9); ground-truth scorecard (band hit rate, profit-range coverage, verdict accuracy, naive-history error) plus a modest Monte Carlo experiment-recovery check; no pass/fail bounds on findings, committed result snapshots instead; results shown in README, notebook and dashboard (aggregates only); small GitHub Actions workflow for tests and export drift.
- [Dashboard UX prototype](issues/07-dashboard-ux-prototype.md): hybrid chosen by the agent under user delegation: story frame (A) -> sticky assumption banner and cockpit grid (B) -> per-item rows with break-even drawn against the hatched assumed band (C); hatching = depends on assumed elasticity; backlog split into "feasible now" and "needs pooling"; amendments recorded on the backlog ticket.
- [Spec: Menu Profitability Simulator (MVP)](../menu-profit-simulator-mvp/spec.md): the destination. Gathers every decision above, includes the README outline and Limitations list, and points at 14 ordered build slices in `../menu-profit-simulator-mvp/issues/` (the last, enabling GitHub Pages, needs a person).
- Destination, scope and priorities were settled in the charting grill (no ticket): spec as the endpoint, parser out of scope, audience = DS/analytics hiring managers, all six features with the priority order above.

## Not yet specified

Nothing. The README narrative and Limitations section and the spec assembly are written (see the spec). The map is complete.

## Out of scope

- **Stretch: LLM invoice/recipe-to-cost parser with eval set** (feature 7): ruled out of this effort; revisit as a fresh effort after the MVP ships. The only MVP obligation is a stable recipe/ingredient-cost schema it could target later.
- **Closing the loop on experiment results** (ingesting a measured elasticity and updating the model automatically): out of scope; the per-item elasticity override covers manual entry.
- Real or downloaded datasets, multi-location restaurants, live POS integration.
