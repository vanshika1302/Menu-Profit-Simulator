# Repo and pipeline architecture

Type: grilling
Status: open
Blocked by: 01, 03

## Question

How do the generator, DuckDB, SQL, notebook and static dashboard fit together, mirroring the Airbnb project's `etl/` -> warehouse -> `sql/` + notebook shape?

Decide: folder layout; tables and which logic lives in SQL vs Python; the single source of truth for simulation math given a static site (precompute scenario grids to JSON vs re-implement the model in browser JS, and how parity is guaranteed); where the dashboard reads data from; how CSVs, the DuckDB file and exported JSON are versioned; how tests run; dependency management.
