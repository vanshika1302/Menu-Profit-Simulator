# Experiment-recovery Monte Carlo

Status: done
Blocked by: 06, 07

## What to build

Add a counterfactual demand function to the generator and run the top five backlog entries, 200 replications each, seed fixed, applying the decision rule; report decision accuracy and interval width at the planned duration. Behind `run_validation.py --full`.

Spec: `../spec.md`.

## Acceptance criteria

- Results snapshotted but checked by the command, not pytest.
- Feeds the notebook and README validation sections.
