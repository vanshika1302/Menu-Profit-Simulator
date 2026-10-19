# How are extracted lines mapped onto the existing ingredient schema?

Type: grilling
Status: open
Blocked by: 01

## Question

Decide: how an extracted line (name, pack size, case price, unit) becomes an `ingredient_costs` row in the ingredient's own unit ($ per lb, qt, each, ...), including the conversion table and what happens when no safe conversion exists; how names are matched to existing `ingredient_id`s versus proposed as new ingredients; what 'effective_week' an invoice line gets; how a recipe line becomes a `recipes` row (qty per serving in the ingredient's unit, handling fractions, ranges and volume-to-weight); and which cases the parser must refuse rather than guess.
