# What does the evidence say about LLM extraction from semi-structured documents, and how should it be evaluated?

Type: research
Status: resolved
Blocked by: 

## Question

Survey current practice for extracting structured rows from invoices and recipes with an LLM: structured-output and schema-constrained decoding, validation and retry patterns, confidence and uncertainty handling, known failure modes (invented quantities, unit and pack-size misreads, silent omissions, prompt injection through document text), and how published work and practitioners evaluate extraction (field-level accuracy, normalised-value scoring, downstream-impact scoring). Report what is established versus anecdotal, so later tickets can set a defensible design. Findings go on a throwaway research branch with a pointer from this ticket.

## Answer

Findings are on the throwaway branch `research/llm-extraction-practice` (commit c37dfca, pushed to origin), file `.scratch/llm-invoice-parser/research/llm-extraction-practice.md` (159 lines). The branch is never merged. The researcher read abstracts and documentation pages, not full paper bodies. Evidence tiers: Anthropic documentation is vendor-established; most extraction benchmarks are preprints on PDF or image pipelines, not clean text; practitioner sources are anecdotal.

What a design ticket can rely on:
- **Structured outputs:** Claude's docs say `output_config.format` with `strict: true` guarantees schema-valid JSON and types. Refusals and `max_tokens` stops can still break the schema, and numeric bounds and string-length limits are not supported, so positivity and range checks must be code. Forced `tool_choice` returned a 400 on the current Claude 5 family per the define-tools docs as fetched during research: use structured outputs, or `auto` with strict tools. Re-check at build time.
- **A schema covers shape only:** invented values, omitted rows and wrong units all pass it. One paper (EMNLP 2024 Industry) reports format restrictions can hurt reasoning; whether that applies to extraction is unverified.
- **Retries:** schema retries are mostly unnecessary under constrained decoding; a retry loop is for semantic failures only, and no measured success rates were found. Deterministic checks are the main lever: quantity times price against the line total, line totals against the subtotal, unit in the known set, evidence quote found in the source text.
- **Confidence:** verbalised confidence is overconfident (Xiong et al., ICLR 2024); Anthropic documents no per-field confidence or logprobs. Suggested instead: flags from check failures, quote-not-found, run-to-run disagreement, and a categorical `ok / ambiguous / missing` status with nullable fields. This is the researcher's inference, to be measured on the synthetic set.
- **Hallucination:** Anthropic's guide recommends permission to say "I don't know", verbatim quotes and per-claim verification; it says these reduce but do not eliminate it, with no numbers. A benchmark preprint scores missing and fabricated values separately and uses per-field metrics (exact, tolerance, semantic); its headline failure rate is on a far larger PDF task and should not be transferred.
- **Prompt injection through document text** is an established threat. A spotlighting study reports attack success falling from over 50% to under 2%, but on GPT models and as a preprint; no residual rate exists for Claude. This tool has no tools, no network and a human approver, so the remaining risk is poisoned or injected rows: show the source evidence beside each staged row and include a few hand-written injection invoices in the evaluation set.
- **Evaluation precedent:** DocILE line-item F1 (micro F1 over line-item fields) is the model for row alignment; Anthropic's eval guidance backs task-specific, code-graded evals with edge cases. **No published standard exists** for normalised-value or downstream-impact (contribution margin, class-flip) scoring: frame the downstream scoring as this project's own method.
- **Unverified, so measure ourselves:** unit and pack-size misread rates (no study found), Claude's abstention quality on invoices, retry effectiveness, and several paper venues and quoted numbers (listed in the findings file).
