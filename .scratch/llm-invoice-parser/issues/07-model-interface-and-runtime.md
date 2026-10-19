# How does the tool call the model, and what runs in tests?

Type: grilling
Status: resolved
Blocked by: 02

## Question

Decide: the single model-call function and its contract; prompt and schema ownership; structured-output and validation-and-retry approach; recorded-response or stub model for tests and CI; API key handling; model choice and its cost and latency for a small eval set; and how the live run is separated from the deterministic evaluation.

## Answer

Settled with the user in a two-round grilling (all eleven recommendations accepted). Built on the extraction-practice research (strict structured outputs guarantee shape only; no usable confidence; forced tool use errors on the current Claude 5 family per the docs as fetched).

**Interface.** One function, `complete_json(system, user, schema) -> dict`, behind a small interface with three implementations: **live** (Anthropic API), **recorded** (replays committed responses) and **stub** (a tiny rule-based extractor for unit tests). The rest of the parser takes the interface as an argument and never imports the SDK.

**Model and mechanism.** Structured outputs (`output_config.format` with `strict: true`). Default model `claude-sonnet-5-5`, overridable by an environment variable; each recording notes the model that made it. The prompt and the JSON schema are versioned files in the repo, not strings in code; the prompt version goes into every recording key. At build time, re-check that structured outputs work on the chosen model.

**Tests and CI.** Tests and CI use the recorded client. A recording is keyed by a hash of the prompt, schema, model and prompt version; if any changes, a missing recording fails loudly and nothing passes silently. A separate `--live` command refreshes recordings and scores the real model; its results are committed as a snapshot checked by the command, not by pytest (as with the MVP's Monte Carlo results).

**Checks and retry.** After the schema: the ticket-03 checks (line total, convertible unit, ingredient exists) plus **the quoted source line must be found in the document text** (whitespace-normalised). At most one retry, only for semantic failures where feedback can help (quote not found, line total mismatch), with the failure fed back; a line that still fails is staged with a flag. The live evaluation reports the retry rate and how often a retry fixes the problem (no published rate exists).

**Untrusted document text** (graduated from the map's fog). The text goes in a clearly delimited data block with an instruction to treat it as data only. The schema and catalogue checks limit what output is possible, the source quote is shown beside every staged row, a few hand-written injection invoices go in the evaluation set, and the README states that this reduces the risk and does not remove it.

**Key, cost and dependency.** The key comes only from `ANTHROPIC_API_KEY`. A live run needs an explicit `--live` flag and refuses to run under pytest or CI; before it starts it prints the number of calls, with a default cap that can be raised. The `anthropic` package goes in a separate optional file, `requirements-parser.txt`, so the base `requirements.txt` and CI are unchanged.

**Output schema.** Two shapes. *Invoice*: supplier, the invoice date as written, and a list of lines, each with description, pack text, ordered and received quantities, unit text, unit and extended price, the matched `ingredient_id` or `NEW`, a `status` of `ok`, `ambiguous` or `missing` (fields may be null), and a verbatim `source_quote`; fee, credit and deposit lines go in a separate list with a category. *Recipe*: dish name, servings, and lines with quantity text, unit text, ingredient text, matched id and a quote. Every quantity and price is a string exactly as written (`"3 lb 6 oz"`, `"$1,234.50"`); code parses them. The model does no parsing or arithmetic.

**Size.** One call per document. A document over a size limit (about 6,000 tokens of text) is refused with a message asking for it to be split. Chunking is out of scope for the first version, and the README says so.

**Settings.** The lowest-variance settings the chosen model documents as supported; the full request is recorded. The live evaluation is run three times once to report how often output changes between repeats.

**Failures.** A refusal, a length-limit stop, an API error or a missing recording is an explicit error: no partial staging file, no silent fallback to the stub. A transient API error (5xx, network) gets one retry after a short wait; a recorded run with a missing recording stops and names the missing key.

**Provenance.** Each run writes a sidecar `<run>.meta.json` next to its staging CSV: model, prompt and schema versions, live or recorded, source-file hash, call count and retries. No comment lines in the CSV.

Carried to other tickets: the evaluation set's size and the cost of a live run (05), scoring with the recorded client and the live snapshot (06), module layout, the CLI and the optional requirements file (08).
