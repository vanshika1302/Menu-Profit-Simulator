# What is in the evaluation set and how is it built?

Type: grilling
Status: resolved
Blocked by: 01, 03

## Question

Decide: how invoices and recipes are generated from the synthetic CSVs with controlled messiness (unit variants, abbreviations, pack sizes, typos, fees, credits); how many cases and in what difficulty tiers; the hand-written hard cases; how ground-truth labels are kept; how the set avoids being trivially easy or tuned to the parser; and where the files live and their size.

## Answer

Settled with the user (all six recommendations accepted).

**Generation.** A deterministic generator, `eval/generate_cases.py` with a fixed seed, renders invoices and recipes from the synthetic CSVs using several supplier-style templates. The true rows come straight from the data (`ingredient_costs` rows for invoices, `recipes` rows for recipes), so every case's answer is known in advance. Prices are rendered to cents; invoice dates map to the Monday `effective_week`.

**Difficulty tiers** (each messiness type labelled "grounded in the formats research" or "guessed", as the research file does). *Invoices:* (1) clean, explicit unit prices; (2) pack notation: case prices, `4/5 LB`, `#10` cans; (3) hard: catch weight with ordered and received weights, supplier name variants, fees, credits and deposits, substitution notes, typos; (4) adversarial: injected instructions, a missing date, unknown units, weight-to-volume traps, ambiguous names. *Recipes:* simple; fractions and compound amounts; ranges, "to taste" and yield mentions.

**Size.** About 60 documents: 40 invoices (10 per tier), 14 recipes and 6 hand-written adversarial cases. One call each, so a full live run is about 60 to 80 calls including retries, under the default cap of 100. This settles the live-run cost question the map had left open.

**Truth.** The generator writes the expected result for every case into `data/eval/truth/`: expected cost rows, expected skipped lines and the flags a trap case should raise. The 6 hand-written cases are labelled by hand. Truth never goes into a prompt.

**No tuning to the test.** Cases are split about 70/30 into a development set and a test set. The prompt is tuned on the development set only; the test set is scored once for the committed snapshot. If the prompt changes after that, a fresh test set is generated with a new seed, and the README says so.

**Files.** Everything is committed under `data/eval/` (`invoices/`, `recipes/`, `truth/`), under 1 MB, rebuilt by one command. Cases use invented supplier names and no real logos or documents.

Carried to other tickets: scoring against these truth files (06), the generator's module placement and the evaluation script (08).
