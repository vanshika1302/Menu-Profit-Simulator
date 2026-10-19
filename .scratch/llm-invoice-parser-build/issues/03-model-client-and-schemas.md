# Model interface, schemas and prompts

Status: ready-for-agent
Blocked by: 01

## What to build

`ingest/model_client.py` with the `complete_json(system, user, schema)` interface and live, recorded and stub clients; versioned prompt and JSON schema files for invoice and recipe; the hash-keyed recording format; the document-size limit; the delimited data block for document text; explicit errors for refusal, length stop, API error and missing recording; one retry on transient API errors; `requirements-parser.txt` with the `anthropic` package.

Spec: `../spec.md`.

## Acceptance criteria

- Live client reads only `ANTHROPIC_API_KEY`, needs `--live`, refuses under pytest or CI, prints the call count and honours a default cap of 100.
- `anthropic` is imported only inside the live client; a test confirms the rest of the package and the test suite never import it.
- A missing recording fails loudly naming its key; changing prompt, schema or model changes the key.
- Output schemas match the spec (strings as written, `ok/ambiguous/missing` status, nullable fields).
- Re-check structured-output support for the chosen model in the Claude docs and note the result in the slice.
