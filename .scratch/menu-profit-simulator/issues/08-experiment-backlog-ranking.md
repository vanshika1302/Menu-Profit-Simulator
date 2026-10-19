# Experiment backlog ranking, guardrails and stop rules

Type: grilling
Status: resolved
Blocked by: 03, 05

## Question

How is the ranked experiment backlog generated and scored?

Decide: experiment types in scope (switchback price test, menu-design test, portion test, others); the ranking score (expected profit upside, uncertainty about elasticity that the test would reduce, cost / risk, duration); how experiments are tied to specific items and to the scenarios; guardrail metrics and their thresholds; stop rules (early stop for harm, futility, sample size); what each backlog entry shows (hypothesis, design, duration, success metric).

## Answer

**Experiment types:** three: switchback price test, menu-design test (description, price format, placement), portion test. Each entry carries an **evidence strength** label: price tests are method-backed (Bojinov et al. 2023); menu-design and portion tests are weak priors (small cafeteria studies, consumption only). The backlog never quotes effect sizes from those studies; it says "effect unknown, test to measure it".

**Candidate generation:** every item with a scenario price change gets a price switchback candidate. Other candidates come from the item's menu engineering class (default mapping, shown as a table in the spec; exact class rules are in the matrix-rules ticket): Plowhorse -> small price rise or portion-down; Puzzle -> menu-design test to lift volume; Star -> guardrail-only unless its break-even elasticity sits inside the band; Dog -> price test or portion-down. Items in the same category can be pooled into one category-level test.

**Ranking score:** score = stake x decision uncertainty x feasibility / risk cost, every factor visible in the entry.
- Stake: largest annualized profit change across the three bands.
- Decision uncertainty: p = share of the low-to-high elasticity band on the "loses money" side of the item's break-even elasticity; uncertainty = 4p(1-p). It is 0 when the answer is the same across the whole band (a test can't change the decision) and 1 when split evenly.
- Feasibility: 0 to 1 from the duration estimate.
- Risk cost: revenue at risk during the test (worst band), scaled by the exposed share of the week.
No weights are tuned and no prior over elasticity is invented.

**Duration and feasibility:** block length one day, whole weeks only, carryover assumed one block (m = 1, an assumption: no source gives m for restaurants). Outcome: item contribution profit per block, with sigma from the synthetic data (labelled an assumption). Sample size from n = 32 sigma^2 / Delta^2 per arm (Kohavi et al. 2009, 95% confidence, 90% power), treating blocks as the independent units. If duration exceeds a 12-week cap the entry is flagged "not feasible alone: pool the category or accept a larger detectable effect" with feasibility near 0, rather than being hidden. The cap and m are editable defaults.

**Guardrails (policy choices, not evidence):** total units sold (traffic proxy), menu-total contribution profit per week, same-category units (cannibalization). Defaults: stop-worthy if total units fall more than 3% or total contribution profit falls more than 2%. The schema is unchanged: there is no covers field, so total units is the traffic proxy (Limitations). Satisfaction, waste and staff load are required in real life but not simulated. Thresholds are shown as editable defaults labelled "policy choice, not evidence".

**Stop rules (pre-registered, checked at whole-week looks):**
- Harm stop: a guardrail beyond its threshold at two consecutive weekly looks, applied only after at least one full week of each arm.
- Cap stop: planned duration or the 12-week cap, whichever comes first.
- No early success stop: the conclusion is read only at the planned end using the design-matched randomization test (Bojinov et al.), which avoids the peeking problem without claiming unverified sequential boundaries.
- Always-valid sequential inference (mSPRT, Johari et al.) is a stretch upgrade, not a claim.

**Backlog entry fields:** rank, score and its four factors; target, type, evidence-strength label; hypothesis in project terms ("Demand for Ribeye is less elastic than -1.3, so a +5% price raises profit", -1.3 being the item's break-even elasticity); design (arms, one-day blocks, randomization, assumed carryover m, whole weeks); duration and feasibility flag; primary metric and minimum detectable effect; guardrails with thresholds; stop rules; decision rule ("if the measured elasticity is above the break-even elasticity, roll out; otherwise revert"); the assumptions the entry depends on (bands, sigma, m), each labelled assumed.

**Live behaviour:** scoring is also ported to the JS model, so changing the substitution slider, bands or price changes re-ranks the backlog live. Per-item constants (sigma, baseline volume) are computed at export. Golden fixtures and the Node parity test from the architecture ticket cover the ranked output too. `sim/experiments.py` is the reference implementation.

**After an experiment:** nothing in the MVP. The optional per-item elasticity override from the simulation model ticket lets a user enter a measured value by hand. Ingesting results and closing the loop is out of scope.

Limitations to carry into the README: total units as traffic proxy, no satisfaction/waste/staff-load, assumed carryover m = 1 and sigma from synthetic data, guardrail thresholds are policy, menu-design and portion evidence is weak, no sequential boundaries claimed.

## Comments

- Amendments from the dashboard prototype (resolved by the agent under the user's delegation on that ticket):
  1. The risk cost in the score must be **normalised** (risk as a share of the item's weekly profit, not dollars), otherwise item size cancels out and entries of different size score alike.
  2. The backlog is shown as two lists: **"Feasible now"** (duration within the 12-week cap) and **"Needs pooling or a larger effect"** (over the cap), each ranked by the score. A single list let near-infeasible tests sit at the top.
  3. The weak-evidence candidates (portion, menu-design) need defensible stake and feasibility inputs in the build; the prototype used placeholder constants, so its ordering between types is not evidence.
- Build-time amendments (2026-10-19, agreed in the build): (4) inside each list, method-backed entries rank ahead of weak-prior entries, with the score ordering within each group; the weak tests' stake is an illustrative sizing and their decision uncertainty is 1.0 by construction, so their scores are not comparable with the price tests'. (5) sigma per block is estimated from week-to-week changes (sd of first differences / sqrt(2) / sqrt(7)), so seasonal drift in the baseline window is not counted as noise.
