# What do real supplier invoices and written recipes look like?

Type: research
Status: resolved
Blocked by: 

## Question

What formats, units and notations must the parser handle? Survey how restaurant supplier invoices (broadline distributors, produce, meat, dairy, beverage) and written recipes are laid out in text form: pack-size notation (e.g. 6/#10, 4/1 GAL, 40 LB CS), catch-weight items, units of measure and abbreviations, case price versus unit price, deposits and fees, credits, substitutions and back-orders, recipe quantity styles (fractions, ranges, 'to taste', volume versus weight), yield and trim. Report what is common versus rare, so later tickets can set a defensible scope. Findings go on a throwaway research branch with a pointer from this ticket.

## Answer

Findings are on the throwaway branch `research/invoice-and-recipe-formats` (commit 9334390, pushed to origin), file `.scratch/llm-invoice-parser/research/invoice-and-recipe-formats.md` (153 lines, 19 cited URLs). The branch is never merged. Source quality is uneven: recipes and yields have primary USDA Child Nutrition sources; for invoices there is **no distributor-owned documentation and no real sample**, so every invoice claim rests on software-vendor help pages and blogs (tagged secondary in the file). "Common" and "rare" below are the researcher's judgments, not measured prevalence. All example documents in the file are constructed and labelled as such.

What a design ticket can rely on:
- **Pack notation** `count/size UNIT` (6/#10, 4/1 GAL, 4/5 LB, 40 LB) is common and usually sits inside the description text. The price is per case, not per lb. `#10` is a can size (about 108 oz per USDA) while `6/10#` is pounds, so the parser needs a small, approximate can-size lookup.
- **Catch weight** (meat, poultry, seafood): ordered in cases, billed per lb on received weight. A line can show both ordered and received weight and a naive parse takes the wrong one. Cost per lb is price per lb times received lb divided by lb, never the case count.
- **Case price, each price and per-lb price all occur.** Split case (EA from a case) is occasional. Produce uses count or bunch inside a case (24 ct), which maps onto head, each and doz.
- **Non-ingredient lines** (fuel surcharge, allowances and prompt-pay discounts, beverage deposits, credits as negative lines) must be recognised and kept out of ingredient costs. Substitutions and shorts are often hand-annotated, so in text they appear only as a changed description or a note line.
- **Names are inconsistent across suppliers** ("onion green iceless", "green onion bunch", "scallion"): matching to `ingredient_id` is a real task, not only unit parsing.
- **Units likely missing from the current list** (inference): fl oz, pint, cup, tbsp, tsp, bunch, kg/g/L, count per case. Volume to weight needs a density the schema lacks.
- **Recipes** (USDA, institutional): compound quantities (`3 lb 6 oz`, `1 gal 2 qt`), Unicode fractions, weight and volume side by side, can references ("1 No. 10 can"). One text export garbled 9 3/8 as "93/8", so fraction handling needs care.
- **Yield and trim:** AP versus EP, yield = EP/AP, cooking loss (USDA: raw ground beef gives 0.75 cooked). The simulator has no yield model, so stage a flag or state a convention, and list it under Limitations.
- **Suggested scope (judgment, not measured):** in scope: pack notation, catch weight, fee and credit recognition, name matching. In scope with a flag: substitutions, back-orders, deposits, ranges, "to taste", volume-to-weight. Out of scope: handwritten notes, EDI, nested packs, yield modelling, metric-only invoices.

Unverified: any prevalence figure; restaurant (as opposed to school-program) recipe style including "to taste" and ranges; back-order line format and nested pack notation; Sysco and US Foods column conventions beyond one Restaurant365 EDI note. Not read: the DLA abbreviation list (403), the PSU recipe-costing chapter (403, search summary only), a Florida keg-deposit statute (redirected). Several secondary pages were seen only as search summaries.
