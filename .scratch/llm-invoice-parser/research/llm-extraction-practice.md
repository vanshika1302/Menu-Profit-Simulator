# Research: LLM extraction practice for invoices and recipes

Ticket: `issues/02-llm-extraction-practice.md` (on main). Researched 2026-10-19.
Method: primary sources (vendor docs, arXiv/ACL papers read at abstract level via fetch). No figure below is
invented; each is attributed. Evidence grades:

- **ESTABLISHED**: vendor documentation of behaviour, or a peer-reviewed paper.
- **PREPRINT**: arXiv only, not peer reviewed (or review not verified).
- **ANECDOTAL**: practitioner blog, vendor marketing, or my own inference. Not evidence of rates.
- **UNVERIFIED**: I looked and could not confirm.

Limit of this pass: I read abstracts and doc pages, not full paper bodies. Numbers the abstract did not state are not
reported. Anthropic docs were read on 2026-10-19 and model support changes often; re-check at build time.

## 1. Structured output and schema-constrained decoding

| Claim | Grade | Source |
|---|---|---|
| Claude offers JSON outputs (`output_config.format`, `type: "json_schema"`) and strict tool use (`strict: true`). Both use grammar-constrained sampling and guarantee schema-valid JSON and types. Page marks it GA. | ESTABLISHED (vendor) | https://platform.claude.com/docs/en/build-with-claude/structured-outputs ; https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use |
| Without strict mode Claude "might return incompatible types (`"2"` instead of `2`) or omit required fields". Strict removes the need to validate and retry for *schema* violations. | ESTABLISHED | strict-tool-use page |
| Not guaranteed: on refusal (`stop_reason: "refusal"`) or truncation (`"max_tokens"`) output may not match the schema; enum/const capitalisation is not guaranteed. | ESTABLISHED | structured-outputs page |
| Unsupported schema features: `minimum`/`maximum`/`multipleOf`, string length limits, recursive schemas; `minItems` only 0 or 1; `additionalProperties` must be `false`. Limits: 20 strict tools, 24 optional params, 16 union params per request. So "qty > 0" cannot live in the schema; it must be code validation afterwards. | ESTABLISHED | structured-outputs page |
| First use of a schema pays grammar-compile latency; compiled grammars are cached 24 h. Changing `output_config.format` invalidates the prompt cache for that thread. | ESTABLISHED | structured-outputs page |
| On Claude Opus 5.5, Sonnet 5.5, Fable 5.1 and Mythos 5.1, forced tool use (`tool_choice` `any` or `tool`) returns a 400 error. Docs say use `auto` with strict tool use, or structured outputs. Forced tool use also skips thinking on models that accept it. | ESTABLISHED (as of fetch date) | https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools |
| Constraining format can hurt reasoning: "Let Me Speak Freely?" (EMNLP 2024 Industry Track) reports a significant decline in reasoning ability under format restrictions, worse with stricter formats. The abstract does not say how extraction tasks fare. | paper ESTABLISHED; applicability to extraction UNVERIFIED | https://aclanthology.org/2024.emnlp-industry.91/ ; https://arxiv.org/abs/2408.02442 |
| JSONSchemaBench: 10,000 real-world schemas, six engines (Guidance, Outlines, Llamacpp, XGrammar, OpenAI, Gemini), scored on efficiency, coverage, quality. Benchmarks engines, not Claude. | PREPRINT | https://arxiv.org/abs/2501.10868 |

Reading for design: schema-constrained output solves *shape* (valid JSON, right types, enum membership) and nothing
about *truth*. Every failure mode in section 4 survives it.

## 2. Validation and retry patterns

- Schema retries are largely unnecessary under constrained decoding (vendor statement above). Retries remain needed for
  refusal, truncation, and semantic failures the schema cannot express. ESTABLISHED (vendor docs).
- Validate, then feed the error back and retry is the common library pattern. Instructor documents it: validate with a
  Pydantic model, on failure send error context back, repeat up to `max_retries`. The page I fetched does not state a
  default retry count (a search snippet said 3; UNVERIFIED). It notes LLM-based semantic validation adds cost and
  latency that compound with retries. ANECDOTAL as to effectiveness (library docs, no measured retry success rates).
  https://python.useinstructor.com/concepts/validation
- Deterministic post-checks are the strongest lever here because the target schema is small and the domain has
  arithmetic identities. Candidates (my inference, ANECDOTAL as a recommendation): `qty * unit_price` equals line
  total; line totals sum to the invoice subtotal; unit is in the known set (lb, qt, gal, oz, each, doz, head);
  converted unit cost within a plausible band of that ingredient's history; quoted evidence is a substring of the
  source text.
- Anthropic's hallucination guide lists: allow "I don't know", extract word-for-word quotes first, verify each claim
  with a supporting quote and retract if none, best-of-N consistency, restrict to provided text. It states these
  "significantly reduce hallucinations, they don't eliminate them". ESTABLISHED (vendor guidance, no measured numbers).
  https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-hallucinations

## 3. Confidence, uncertainty and abstention

- Verbalised confidence is overconfident. Xiong et al., ICLR 2024: black-box LLMs "tend to be overconfident" when
  verbalising confidence; consistency across samples and better prompts help; no technique consistently wins; all
  struggle on tasks needing specialised knowledge; white-box methods are only modestly better. ESTABLISHED.
  https://arxiv.org/abs/2306.13063
- Tian et al. (arXiv 2305.14975) report RLHF models verbalise better-calibrated confidence than their token
  probabilities. Venue not verified: PREPRINT. Its emphasis differs from Xiong; I could not resolve the tension for our
  case. https://arxiv.org/abs/2305.14975
- I did not find a documented per-field confidence or log-probability output in the Anthropic pages I read.
  UNVERIFIED (absence of evidence).
- Implication (inference, ANECDOTAL as a design claim): do not treat a self-reported 0..1 confidence as a calibrated
  probability. More defensible uncertainty signals, roughly in order of trust: (1) deterministic check failures;
  (2) quote-not-found in the source; (3) disagreement across repeated runs (Xiong's consistency idea, Anthropic's
  best-of-N); (4) the model's own categorical flag with a reason. Score the flag empirically on the synthetic set
  (does a flag precede an error?) instead of assuming it works.
- Abstention: vendor guidance is to give explicit permission to say information is missing. Schema-wise, make fields
  nullable and add an enum like `status: ok | ambiguous | missing`, so "not in the document" has a legal value.
  ExtractBench scores missing versus fabricated separately (section 5). How well Claude abstains on invoices
  specifically: UNVERIFIED; test it on our set.

## 4. Known failure modes

The categories are well documented. Rates for invoice and recipe unit or pack-size errors are not.

| Failure | What the evidence supports | Grade |
|---|---|---|
| Invented quantities or values | Anthropic acknowledges hallucination and that mitigations do not eliminate it. ExtractBench defines a hallucination error as gold null but model produced a value, and reports leading models (GPT-5/5.2, Gemini-3, Claude 4.5 Opus/Sonnet) unreliable on realistic schemas, "0% valid output on a 369-field financial reporting schema across all tested models". That is PDF-to-JSON on a far bigger schema than ours; do not transfer the number. https://arxiv.org/abs/2602.12247 | vendor ESTABLISHED; ExtractBench PREPRINT |
| Silent omissions | ExtractBench separates omission (gold has a value, prediction MISSING) from fabrication. A table-reading preprint (arXiv 2606.32029, seen only as a search snippet, not fetched) says models incorrectly cite or omit table values across 1.7B to 20B parameter models. Omission is what a schema cannot detect: valid JSON with fewer rows. | PREPRINT |
| Unit and pack-size misreads (for example "6/#10 cans", "2x5 lb", "doz" vs "each", oz weight vs fl oz) | I found no peer-reviewed or vendor study measuring this for LLM extraction. Invoice benchmarks score fields like totals, dates, vendors; DocILE line items are description, quantity, price tuples scored by F1, with no unit-conversion metric. Treat unit and pack arithmetic as a risk we must measure ourselves. Same for recipe measures. | UNVERIFIED |
| Truncation or refusal yielding non-conforming output despite strict mode | Vendor docs (section 1). | ESTABLISHED |
| Input modality | A preprint on eight multimodal models and three public invoice datasets found native image input generally beat document-to-markdown conversion. We are text-only by decision, but it means published invoice accuracies mostly come from image or OCR pipelines, not clean text. https://arxiv.org/abs/2509.04469 | PREPRINT |
| Prompt injection via document text | Below. | threat ESTABLISHED; rates ANECDOTAL/none |

### Prompt injection

- Threat class: Greshake et al. (arXiv 2302.12173; reported as AISec '23, venue per search result, not verified on the
  ACM site) show instructions hidden in data an LLM processes can redirect LLM-integrated applications, and said
  effective mitigations were then lacking. https://arxiv.org/abs/2302.12173
- Anthropic's guide distinguishes indirect injection (trusted user, untrusted third-party content such as documents).
  Its advice: deliver untrusted content in `tool_result` blocks, say what the content is and where it came from, state
  an untrusted-content policy in the system prompt, JSON-encode untrusted strings, send your own instructions in a user
  turn after the result, apply least privilege, optionally pre-screen with a small classifier call, and red-team with
  injection-bearing documents.
  https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/mitigate-jailbreaks
  The guide says Claude is "inherently resilient" yet still prescribes layers; no residual rate is published.
- Spotlighting (Microsoft, arXiv 2403.14720): input transformations that signal provenance cut attack success from
  more than 50% to below 2% on GPT-family models with minimal task impact. PREPRINT; other vendor's models; the
  abstract says nothing on adaptive attackers. https://arxiv.org/abs/2403.14720
- Practitioner view (ANECDOTAL): Simon Willison's "lethal trifecta" (private data, untrusted content, external
  communication) argues guardrails are insufficient and the safe move is architectural: remove one leg.
  https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/
- Fit to this project: the parser has no tools, no network, no write access, and a person approves staged rows. That
  removes the exfiltration and action legs. Remaining risk is data poisoning: an invoice line saying "set price to
  0.01" or an injected extra row. Defence is structural: model returns only schema-typed rows, staged rows cannot
  trigger actions, and approval shows source evidence beside each row. OWASP LLM01 guidance (privilege control, human
  approval) agrees, but I saw it only via secondary summaries (UNVERIFIED as primary).

## 5. How extraction is evaluated

- Per-field metric. ExtractBench (preprint) treats the schema as an executable spec: each field declares its metric
  (exact for identifiers, tolerance for quantities, semantic equivalence for names), arrays are aligned, missing is
  separated from fabricated. 35 PDFs, 12,867 evaluatable fields. https://arxiv.org/abs/2602.12247
- Line-item scoring. DocILE (arXiv 2302.05658) defines Line Item Recognition: group fields into line items
  (description, quantity, price) and report micro F1 over line-item fields; KILE uses average precision. 6.7k
  annotated documents. A template for matching rows before comparing fields. Venue not verified (search snippet).
  https://arxiv.org/abs/2302.05658
- Invoice benchmarks report field-level precision, exact-match accuracy and consistency-check failure rates
  (arXiv 2510.15727: 94% overall, line items about 91%, 93% of consistency checks passed, as quoted in a search
  snippet; preprint; dataset not described in the abstract. Illustrative only, not a baseline).
  https://arxiv.org/abs/2510.15727
- Anthropic eval guidance: task-specific evals including edge cases, automate grading, prefer volume over hand-grading,
  multidimensional criteria including error severity. ESTABLISHED (vendor).
  https://platform.claude.com/docs/en/test-and-evaluate/develop-tests
- Normalised-value scoring and downstream-impact scoring: I found no published standard for either in invoice
  extraction. Closest are ExtractBench tolerance ranges and rule-based consistency checks. Scoring by effect on a
  business quantity (here contribution margin and menu-class flips) looks like this project's own method; say so in the
  README. UNVERIFIED as established practice.
- LLM judges: a vendor blog on judge false positives for table OCR exists
  (https://reducto.ai/engineering/posts/llm-judges-table-ocr-false-positives/); I did not read it. ANECDOTAL and
  vendor-interested. With synthetic ground truth, code grading suffices and no judge is needed.

## 6. What the design tickets should take from this

1. Use structured outputs (`output_config.format`) or `auto` plus strict tool use. Do not rely on forced `tool_choice`
   (400 on Sonnet 5.5 per current docs). Treat `refusal` and `max_tokens` as explicit errors. (ESTABLISHED)
2. Schema gives shape only. Put positivity, unit-set and total-reconciliation checks in code, since the schema cannot
   express numeric bounds. (ESTABLISHED docs plus inference)
3. Have every extracted number carry a verbatim `evidence` quote and check it is a substring of the source; use
   nullable fields and an explicit `missing/ambiguous` status. (vendor guidance ESTABLISHED; effect on our data must be
   measured)
4. Do not use self-reported confidence as a probability. Flag from deterministic failures, quote-not-found and, if
   budget allows, run-to-run disagreement; measure whether flags precede errors. (ESTABLISHED overconfidence)
5. Guard against omission: reconcile row count and totals; score omissions separately from fabrications.
6. Injection: no tools, no network, human approval, delimited or JSON-encoded document text, untrusted-content policy
   in the system prompt, a few hand-written injection invoices in the eval set. No residual-rate claim exists; state
   the limitation plainly.
7. Eval: per-field metrics (exact for ids and units, tolerance for quantities), DocILE-style row alignment, separate
   omission, fabrication and wrong-value counts, plus the project's own CM and class-flip scoring labelled as a method
   choice.
8. Must be measured by us (unverified): unit and pack-size misread rates; Claude's abstention quality; retry
   effectiveness; whether format constraints cost accuracy on extraction.

## Source index

Anthropic docs (all under https://platform.claude.com/docs/en/): structured-outputs, strict-tool-use, define-tools,
reduce-hallucinations, mitigate-jailbreaks, develop-tests (full paths in the sections above).
Papers (arxiv.org/abs/ID): 2408.02442 (EMNLP 2024 Industry), 2306.13063 (ICLR 2024), 2302.12173, 2403.14720,
2305.14975, 2501.10868, 2602.12247, 2302.05658, 2510.15727, 2509.04469, 2606.32029.
Practitioner: Instructor docs, Willison blog, Reducto blog (unread).
