# What is a staged row, and how does a person approve it?

Type: grilling
Status: resolved
Blocked by: 03

## Question

Decide: the staging file format (fields, flags, reasons, confidence if any, source line reference); what counts as uncertain enough to flag; the review step a person performs and its form (CLI prompts, an edited file, a diff); how approved rows merge into the CSVs and the warehouse and how the pipeline re-runs; handling of duplicates, conflicts with existing rows and rollback; and what stays in version control.

## Answer

Settled with the user in a two-round grilling (all ten recommendations accepted).

**Where approved rows land.** An overlay folder, `data/approved/`, with the same three CSV shapes (`ingredients`, `recipes`, `ingredient_costs`). `data/synthetic/` belongs to the generator (it is rewritten by `etl/generate.py` and a test checks the committed CSVs against it byte for byte), so the synthetic base is never edited. The loader reads the base, then the overlay: a cost row for the same ingredient and week replaces the base row; an approved recipe replaces all base rows for that dish; new ingredients are appended.

**Opt-in.** The overlay merge is off by default: `load_all(..., with_approved=True)` and a `--with-approved` pipeline flag. Every committed artifact (`index.html`, notebook, golden fixtures, validation snapshots) is built from the synthetic base only, so approving rows never makes CI drift. The parser's own demo (invoice, staged rows, approval, re-run with the flag) uses the flag.

**Staging file.** One CSV per parse run, one row per proposed item. Columns: `row_id`, `kind` (`ingredient`, `recipe_line`, `cost`), `status` (`proposed`, `flagged`, `skipped`), the target fields for that kind, `flags`, `reason` (one plain sentence), `source_line`, `source_quote`, `decision` (blank until the reviewer fills it) and `corrected_value`. Skipped lines (fees, credits, etc.) appear as `skipped` rows with a category. Staging files live in an ignored folder, `data/staging/`.

**Flag vocabulary (closed set).** `needs_cost`, `check_failed`, `ambiguous_name`, `new_ingredient`, `conflict`, `update`, `unconvertible_unit`, `missing_date`, `missing_servings`, `range_midpoint`, `no_yield_applied`, `skipped_line`, plus `edited` (added when a reviewer corrects a value). A row can carry several.

**Review step.** The reviewer edits the `decision` column (`approve` or `reject`) and any `corrected_value`, then runs an `apply` command that prints a summary and diff and writes nothing by default; `--write` applies it. Flagged rows sort first and every row shows its source quote. There are no interactive prompts in the first version. There is **no bulk approval**: every row needs an explicit `approve`, and a blank decision means no change.

**Corrections.** `corrected_value` may fix a unit cost, a quantity or an ingredient id. Code re-checks it (ingredient exists, numbers positive, unit convertible); the row gets the `edited` flag and the approval log records both original and corrected value.

**Precedence and audit.** The overlay beats the base; a later approved run beats an earlier one for the same key. Every approval is appended to `data/approved/approvals.csv` (run id, row id, kind, key, decision, approval time, source-file hash, original and corrected value). There is no in-tool rollback: undo a run by deleting its rows from the overlay or with `git revert`; the log lists which rows to remove.

**Idempotence.** `row_id` is a hash of the source file, line number and kind, so re-parsing the same file yields the same ids and applying decisions for an id a second time is a no-op that reports "already applied".

**Version control.** Ignored: `data/staging/` and `data/approved/` (real invoices may be private). Committed: the synthetic evaluation invoices and recipes, and one small demo overlay under `data/demo_approved/` generated from the synthetic data so the notebook and README can show the whole path.

Carried to other tickets: the evaluation set's files and size (05), scoring flags and edits (06), the model's output schema (07), module layout, the `apply` command and loader change (08).
