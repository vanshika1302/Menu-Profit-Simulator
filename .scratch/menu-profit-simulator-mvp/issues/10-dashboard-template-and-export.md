# Dashboard template and export to root index.html

Status: ready-for-agent
Blocked by: 07, 09

## What to build

`dashboard/template.html` and `scripts/export_dashboard.py` rendering a self-contained root `index.html` with the data inlined, built to the dashboard UX ticket (hybrid layout, hatching rules, items view and drawer, two backlog lists, dark mode, narrow-screen stacking) with validation aggregates (aggregates only).

Spec: `../spec.md`.

## Acceptance criteria

- Works opened as a file.
- Leakage scan of `index.html` passes.
- Review against the dashboard UX ticket and the prototype branch `prototype/dashboard-ux` (reference only; rewrite properly).
- Headless render check at desktop and phone width.
