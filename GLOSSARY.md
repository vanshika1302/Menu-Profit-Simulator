# Glossary

**Contribution margin (CM)**: an item's selling price minus its ingredient cost, per unit sold.

**Menu engineering class**: an item's classification by popularity and contribution margin: **Star** (high popularity, high CM), **Plowhorse** (high popularity, low CM), **Puzzle** (low popularity, high CM), **Dog** (low popularity, low CM).

**Elasticity band**: a low / medium / high assumed range for how much demand falls when price rises. An assumption, never a measured fact, until an experiment measures it.

**Break-even volume drop**: the largest fractional fall in units sold a price increase can absorb before profit stops improving. Equals the price increase divided by the new contribution margin.

**Substitution share**: the share of buyers lost to a price change who switch to another menu item instead of leaving.

**Ingredient-cost shock**: a percentage change in the cost of an ingredient (e.g. beef +20%) that flows through recipes into item costs.

**Guardrail metric**: a measure that an experiment must not harm (e.g. covers, average check), watched alongside the target metric.

**Stop rule**: a predefined condition under which an experiment is ended early.

**Ground truth**: the true elasticities and substitution patterns the synthetic restaurant's generator used to produce its sales. Kept apart from the user-facing data and never seen by the simulator or dashboard; used only to score whether the simulator's bands and simulated experiments recover it.

**Break-even elasticity**: for a given price change, the elasticity at which profit is unchanged. Demand less elastic than this makes the change pay off; more elastic makes it lose money.

**Baseline**: the reference weekly units, prices and costs a scenario is compared against: the trailing 12 weeks of the synthetic sales.

**Scenario**: a set of ingredient-cost shocks, per-item price changes and a substitution share, evaluated against the baseline under each elasticity band.

**Popularity threshold**: the unit share an item must reach within its scope (a category, or the whole menu) to count as popular: 70% of an equal share by default.

**Margin threshold**: the unit-weighted average contribution margin of the scope; an item at or above it counts as high margin.

**Class uncertain**: a flag on an item whose menu engineering class differs between the low, medium and high elasticity bands.

**Validation scorecard**: the aggregate measures, computed against the ground truth, of how well the simulator's bands, ranges and verdicts hold up on the synthetic restaurant.

**Staged row**: a row the invoice or recipe parser proposes for the ingredient, recipe or cost data, held in a staging file with a flag and a reason on anything uncertain. It changes nothing until a person approves it.

**Pack size**: how a supplier packages a purchase: a count of units of a given size in one case, written like `4/5 LB` (four 5-lb units). A case price is the price of the whole case, not of one unit.

**Catch weight**: an item billed by the weight actually received rather than by the case count, so the cost per pound comes from received weight.

**Approved overlay**: the person-approved rows from the invoice and recipe parser, kept apart from the generated synthetic data and merged over it only when asked for.
