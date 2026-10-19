# Enable GitHub Pages (needs a person)

Status: done
Blocked by: 13

## What to build

In the repo settings, serve GitHub Pages from `main` at the root, confirm the live URL loads `index.html`, and add the link to the README.

Spec: `../spec.md`.

## Acceptance criteria

- Live URL opens the dashboard.
- README link updated.

## Comments

- Pages enabled from `main` at `/` via the GitHub API on 2026-10-19; the live URL serves a page byte-identical to the committed `index.html`. The README link already pointed at it.
