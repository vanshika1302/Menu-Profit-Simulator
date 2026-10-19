# Simulation model core (Python, pure functions)

Status: ready-for-agent
Blocked by: 01

## What to build

`sim/model.py`: constant-elasticity demand, cost shock through recipes, same-category substitution and cannibalization (single pass), break-even drop (with and without substitution), break-even elasticity.

Spec: `../spec.md`.

## Acceptance criteria

- Plain data in, plain data out; no DuckDB access.
- pytest identities: profit unchanged at eps*; at exactly the break-even drop profit is unchanged with and without substitution; at s = 0 net equals dP / (CM + dP); substitution conservation; price-cut mirror; 0% shock changes nothing; shocking an ingredient moves exactly its recipes; zero change returns the baseline.
- A few hand-computed examples.
