# Synthetic restaurant design and hidden ground truth

Type: grilling
Status: resolved
Blocked by:

## Question

What synthetic restaurant do we generate, and should the generator embed **known, hidden** elasticities and substitution patterns?

Decide: restaurant concept and the ~30 items (categories, price points); ingredient list and recipe (bill-of-materials) schema; weekly sales structure (seasonality, trend, promo noise, 12 months); whether true per-item elasticities / substitution structure are baked in as hidden ground truth (so later work can check the simulator and experiments recover them) and, if so, how they stay out of the user-facing tables; the CSV file set and column schemas; seed and size limits. The recipe/ingredient-cost schema must stay stable enough for a future invoice parser to target.

## Answer

**Concept:** casual full-service American bistro, 30 items in 6 categories (base prices in $):
- Starters (5): Wings 13, Fried Calamari 14, Loaded Nachos 13, Soup of the Day 8, Caesar Salad 11
- Burgers and sandwiches (5): Classic Burger 15, Bacon Cheeseburger 17, Veggie Burger 14, Chicken Sandwich 14, Philly Cheesesteak 16
- Entrees (7): Ribeye 38, Sirloin 28, Salmon 27, Chicken Parm 22, Short Rib 31, Mac and Cheese 16, Fish and Chips 20
- Pasta and bowls (4): Spaghetti Bolognese 19, Shrimp Scampi 24, Chicken Alfredo 20, Grain Bowl 16
- Desserts (4): Cheesecake 9, Brownie Sundae 9, Key Lime Pie 8, Churros 8
- Drinks and sides (5): Fries 6, Side Salad 6, Soda 3.50, Draft Beer 7, House Wine 9

Seven items contain beef, so the beef cost shock moves several quadrants. Volumes and food-cost percentages are tuned so all four menu engineering classes are populated (roughly 6-8 items each).

**Schema (five small CSVs):** `menu_items` (item_id, name, category, base_price); `ingredients` (ingredient_id, name, unit); `recipes` (item_id, ingredient_id, qty_per_serving); `ingredient_costs` (ingredient_id, effective_week, unit_cost; a history); `weekly_sales` (week_start, item_id, units_sold, avg_selling_price). `ingredients`, `ingredient_costs` and `recipes` stay narrow and stable as the target for a future invoice/recipe parser.

**Price history:** modest and noisy on purpose: 4-5 items get a 5-8% price rise mid-year and there are two short promos, confounded with seasonality. Too few changes to pin elasticity down, which is the project's thesis: history gives a noisy hint and an experiment is needed.

**Hidden ground truth:** yes, in a separate validation-only `ground_truth.csv`, never read by the simulator or dashboard.
- True own-price elasticity by category: Drinks and sides about -0.4, Starters -0.8, Burgers -0.9, Pasta and bowls -1.0, Desserts -1.1, Entrees -1.4, each item jittered by about +/-0.25.
- True substitution: 30-50% of lost buyers switch within the same category, split in proportion to popularity; about 10% cross to other categories; the rest leave.
- Two or three items deliberately fall outside the simulator's low-to-high band so validation shows honest misses.
- These numbers are **authored, not empirical**: the research evidence is thin (see the elasticity benchmarks ticket). The README must say the data is synthetic and the truth is used only for scoring.

**Demand generation:** per item and week: base level, category-level seasonality (summer patio lift for drinks, winter lift for soups and comfort food), small trend, holiday dip, negative-binomial noise, plus price and promo effects from the ground truth. 52 weeks x 30 items = 1,560 sales rows. Seed 42, one `generate` command rebuilds everything. All CSVs under ~500 KB.

**Location:** CSVs are committed under `data/synthetic/` (including `ground_truth.csv`, labelled validation-only). `.gitignore` is unchanged: `data/raw/` and `*.duckdb` stay ignored.

Left to the build (generator-owned detail, not a decision): the exact ingredient list (~35 ingredients with units), per-item volumes and cost percentages, and the specific promo and price-change dates.
