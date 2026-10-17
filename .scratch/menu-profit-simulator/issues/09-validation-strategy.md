# Validation strategy

Type: grilling
Status: resolved
Blocked by:

## Question

How does the build prove the simulator is right and honest? Decide: unit tests for the formulas (break-even drop, break-even elasticity, cost-shock flow, substitution allocation, price-cut cannibalization); what is checked against the hidden ground truth (e.g. share of items whose true elasticity falls inside the low-to-high band; whether the band-range profit change covers the truth-based change; whether simulated experiments recover the truth); where those checks run (tests vs notebook) and how results are shown in the README as limits rather than boasts; pass/fail thresholds, if any; and how the validation file is kept from leaking into the simulator.

## Answer

**Formula tests (pytest, algebraic identities plus hand-computed examples):**
- Break-even elasticity: at eps*, the price change leaves profit unchanged (to tolerance).
- Break-even drop: at exactly the break-even drop, profit is unchanged, with and without substitution; at s = 0 the net version equals dP / (CM + dP).
- Substitution conservation: lost units = substituted + departed units; destination shares sum to 1.
- Price-cut mirror: cannibalized + new units = volume gained.
- Cost shock: a 0% shock changes nothing; shocking an ingredient moves exactly the items whose recipes use it.
- Zero change returns the baseline; class thresholds are invariant to item order.
- A few small hand-computed examples anchor the exact values.

**Data and SQL tests:** generator: same seed gives byte-identical CSVs; schemas match the synthetic restaurant ticket; about 1,560 sales rows; total CSV size under ~500 KB; no negative units or costs; food-cost % roughly 20-45%; all four menu engineering classes appear. SQL: each view (item cost, CM, 12-week baseline, popularity share, matrix inputs) is cross-checked against an independent pandas computation on the same CSVs.

**Leakage tests (no ground truth reaches the simulator or dashboard):** an import check, plus a runtime test: run the simulator and export with `ground_truth.csv` removed or replaced by garbage and assert identical outputs; and scan the exported `index.html` for the ground-truth file's column names and the exact per-item true elasticity values (aggregates are allowed).

**Parity fixtures:** a few dozen golden scenarios from `scripts/make_golden.py`, committed: no change, single price rise, price cut, category-wide change, beef shock, combined shock and price, substitution at 0%, 25% and 100%, each band, per-category overrides, edge cases (insufficient-data item, a price change at the break-even). Each covers model outputs, classes and the ranked backlog. Tolerance: relative 1e-9 on numbers, exact on classes and ranks.

**Ground-truth scorecard (`sim/validation.py`, the only reader of ground truth):**
- Band hit rate: share of items whose true elasticity lies inside the low-to-high band (expected roughly 80%, about five misses, mostly drinks and sides).
- Profit-range coverage: for a standard scenario set (e.g. +5% and +10% on each item), the share where the true-elasticity profit change lies inside the simulator's low-to-high range.
- Verdict accuracy: how often each verdict agrees with the truth-based sign; the costly error is "pays off under all bands" when the truth says it loses money.
- Naive history estimate: a simple before/after elasticity estimate for the 4-5 items with price changes in the history, with its error against the truth (the project's central claim in one chart).

**Experiment-recovery simulation:** a modest Monte Carlo: top five backlog entries, 200 replications each, seed fixed, using a counterfactual demand function added to the generator. Apply the decision rule (roll out if measured elasticity beats the break-even elasticity), compare with the truth, report decision accuracy and interval width at the planned duration. Results in the notebook and README; not in the dashboard or pytest (slow).

**Thresholds:** none on the scorecard findings (a bound would invite tuning bands or generator until a number passes). Instead the fast scorecard metrics are saved to a committed `validation_results.json`; a test recomputes them and fails on any difference beyond a tight tolerance, so a change that moves results must be noticed and re-recorded on purpose. Monte Carlo results are snapshotted too but checked by the validation command, not by pytest.

**Organization and run:** `sim/validation.py` computes scorecard and recovery. `scripts/run_validation.py` runs the fast scorecard (seconds) and writes `validation_results.json`; `--full` adds the Monte Carlo. pytest runs formula, data, SQL, leakage and snapshot tests and stays fast. The Node parity check stays separate (architecture ticket). The notebook presents results from the saved files.

**Presentation and framing:** README has a validation section with the scorecard table and recovery results, framed as: synthetic data and authored truth, so this shows the method works and where it fails, not real-world accuracy; misses are shown. The notebook has the full scorecard and charts including the naive-history error. The dashboard has a short "How well does this work? (synthetic data)" section with aggregates only; per-item true elasticities never appear.

**CI:** a small GitHub Actions workflow (`.github/workflows/test.yml`) runs pytest and the Node parity check on every push and pull request, and checks that the committed `index.html` matches a fresh export. No secrets or paid services. Pages still serves root `index.html` from `main`; no deployment action.
