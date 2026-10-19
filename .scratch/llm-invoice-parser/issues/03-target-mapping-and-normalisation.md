# How are extracted lines mapped onto the existing ingredient schema?

Type: grilling
Status: resolved
Blocked by: 01

## Question

Decide: how an extracted line (name, pack size, case price, unit) becomes an `ingredient_costs` row in the ingredient's own unit ($ per lb, qt, each, ...), including the conversion table and what happens when no safe conversion exists; how names are matched to existing `ingredient_id`s versus proposed as new ingredients; what 'effective_week' an invoice line gets; how a recipe line becomes a `recipes` row (qty per serving in the ingredient's unit, handling fractions, ranges and volume-to-weight); and which cases the parser must refuse rather than guess.

## Answer

Settled with the user in a two-round grilling (all eleven recommendations accepted).

**Division of labour.** The model reads text and copies out raw fields only: description, pack text (e.g. `6/#10`, `4/5 LB`), quantity, unit text, prices, the line total, and a verbatim quote of the source line. **Code does all unit conversion and cost arithmetic** and checks quantity x price against the line total. The model never converts or computes a cost.

**Unit conversion.** Exact factors within one dimension: weight (oz, lb, g, kg), volume (fl oz, cup, pint, qt, gal, L), count (each, doz). A small, approximate can-size table (a `#10` is about 108 fl oz) applies only when the ingredient's own unit is a volume. Weight-to-volume and count-to-weight are refused with a flag; there is no density table. An ingredient's own unit stays one of the existing seven (lb, qt, gal, oz, each, doz, head); the conversion table understands more invoice units than that, and an input unit that cannot be converted to the ingredient's unit is flagged. A new ingredient the parser proposes must use one of the seven.

**Pack size and catch weight.** A case line's unit cost is case price divided by (count x size) converted to the ingredient's unit (`4/5 LB` at $38 is 20 lb, $1.90 per lb). A catch-weight line is billed per lb on received weight, so its unit cost is the billed price per lb; where both ordered and received weights are shown, received wins; a catch-weight line with no received weight is flagged and gets no cost.

**Name matching.** The prompt carries the ingredient catalogue (id, name, unit). The model returns an existing `ingredient_id` or `NEW` plus the quoted supplier text. Code checks that the id exists. Ambiguous matches are flagged; there is no fuzzy auto-merge. A `NEW` becomes a staged new ingredient with a proposed id and unit for a person to approve.

**Effective week.** The Monday of the week containing the invoice date. A missing or unreadable date is flagged; it never defaults to today.

**Non-ingredient lines.** Fuel surcharges, allowances, prompt-pay discounts, deposits and credits are recognised and listed in the staging file as skipped lines with a category, so a reviewer sees nothing was lost. They never produce a cost row, and a credit is never applied as a negative cost.

**Duplicates and conflicts.** One staged row per ingredient and week. Where quantities are known the parser proposes the quantity-weighted average, flagged as a conflict. A row that would replace an existing CSV row is staged as an "update", flagged, never silently overwritten; the reviewer decides.

**Recipes.** The dish must match an existing `item_id`; the parser never invents menu items (they need a category and a price). Code parses fractions, Unicode fractions, mixed numbers and compound amounts (`3 lb 6 oz`). Quantity per serving is total divided by servings; missing servings is flagged and the row left unfilled. A range stages the midpoint with a flag; "to taste" and other unquantified lines are skipped with a note. Ingredient names match by the invoice rule above.

**Yield and trim.** The staged quantity is recorded exactly as written. If the recipe mentions yield, trim, edible portion or cooked weight the row gets a "no yield applied" flag, and the README states the limitation.

**Dropped versus flagged.** Where no cost can be computed (missing pack size, unknown unit, weight-to-volume, unknown can size, non-positive price or quantity) the result is a flagged staged row with no value, so a reviewer can fill it in. Where a cost exists but a check disagrees (quantity x price against the line total beyond max($0.02, 0.5%)) the computed row is staged with a "check failed" flag and both numbers shown. Nothing is silently dropped.

Carried to other tickets: the staged row's fields and the review step (04), the generator's messiness types matched to this rule set (05), scoring flags versus silent errors (06), the model's output schema and the evidence-quote check (07).
