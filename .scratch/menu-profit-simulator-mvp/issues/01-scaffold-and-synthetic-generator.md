# Scaffold the repo and generate the synthetic restaurant

Status: ready-for-agent
Blocked by: 

## What to build

Create the folder layout, `requirements.txt`, and `etl/generate.py` (seed 42) producing the five CSVs and the validation-only `ground_truth.csv` under `data/synthetic/`.

Spec: `../spec.md`.

## Acceptance criteria

- Layout matches the architecture ticket; `requirements.txt` lists pandas, numpy, duckdb, matplotlib, jupyter, nbconvert, pytest.
- 30 items, 6 categories, ~35 ingredients, recipes with seven beef items, 52 weeks of sales, an ingredient-cost history, 4-5 mid-year price rises and two promos.
- Ground truth authored as in the synthetic restaurant ticket (category elasticities with jitter; 30-50% within-category substitution).
- pytest: same seed gives identical CSVs; schemas; ~1,560 sales rows; size under ~500 KB; no negative units or costs; food-cost 20-45%; all four classes appear in the trailing 12 weeks (tune volumes; remember the 70% rule is lenient).
