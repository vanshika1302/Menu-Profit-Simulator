# GitHub Actions workflow

Status: done
Blocked by: 09, 10

## What to build

`.github/workflows/test.yml`: pytest, the Node parity check, and a check that the committed `index.html` matches a fresh export.

Spec: `../spec.md`.

## Acceptance criteria

- No secrets or paid services.
- Passes on a clean push.
