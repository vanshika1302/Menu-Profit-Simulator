# Executed analysis notebook

Status: done
Blocked by: 05, 06, 07, 08

## What to build

`notebooks/menu_profit_analysis.ipynb`: imports `sim/`, queries DuckDB through the warehouse function, defines no formulas, committed fully executed. Story: baseline margins and matrix, a beef shock, price scenarios with band ranges and break-even elasticity, the substitution slider, the backlog, validation results including the naive-history error.

Spec: `../spec.md`.

## Acceptance criteria

- Runs top to bottom from a clean checkout after the pipeline.
- All outputs committed.
