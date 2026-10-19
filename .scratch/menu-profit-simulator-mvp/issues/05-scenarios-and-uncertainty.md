# Scenario engine and uncertainty outputs

Status: done
Blocked by: 03, 04

## What to build

`sim/scenarios.py`: a scenario (cost shocks, per-item or per-category price changes, substitution share, bands, optional overrides) evaluated against the baseline under each band, with per-item and menu-total outputs, band ranges, break-even drop versus predicted drop, break-even elasticity and verdicts.

Spec: `../spec.md`.

## Acceptance criteria

- Output fields as in the simulation model ticket.
- Verdicts: pays off under all bands / only if less or more elastic than X / loses under all bands.
- Cost shock with no price change returns identical results for all bands.
