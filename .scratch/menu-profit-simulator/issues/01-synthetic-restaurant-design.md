# Synthetic restaurant design and hidden ground truth

Type: grilling
Status: open
Blocked by:

## Question

What synthetic restaurant do we generate, and should the generator embed **known, hidden** elasticities and substitution patterns?

Decide: restaurant concept and the ~30 items (categories, price points); ingredient list and recipe (bill-of-materials) schema; weekly sales structure (seasonality, trend, promo noise, 12 months); whether true per-item elasticities / substitution structure are baked in as hidden ground truth (so later work can check the simulator and experiments recover them) and, if so, how they stay out of the user-facing tables; the CSV file set and column schemas; seed and size limits. The recipe/ingredient-cost schema must stay stable enough for a future invoice parser to target.
