"""Generate the synthetic bistro: five CSVs plus the validation-only ground truth.

One command rebuilds everything from seed 42:

    python etl/generate.py

The ground truth (true elasticities and substitution shares) is AUTHORED, not
empirical. It is written to ground_truth.csv, which only sim/validation.py may
read. `base_price` in menu_items is the launch price; later price rises and
promos appear only in weekly_sales.avg_selling_price.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
N_WEEKS = 52
FIRST_WEEK = pd.Timestamp("2025-01-06")  # a Monday
OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "synthetic"

# Supply prices are scaled up so food cost lands in a realistic bistro range
# (portions here are plated weights, with no separate waste or yield model).
COST_SCALE = 1.6

# ingredient_id: (name, unit, starting unit cost)
INGREDIENTS = {
    "ribeye": ("Ribeye steak", "lb", 14.0),
    "sirloin": ("Sirloin steak", "lb", 9.0),
    "short_rib": ("Beef short rib", "lb", 8.0),
    "ground_beef": ("Ground beef", "lb", 5.5),
    "shaved_beef": ("Shaved beef", "lb", 8.0),
    "bacon": ("Bacon", "lb", 6.0),
    "chicken_breast": ("Chicken breast", "lb", 3.2),
    "chicken_wings": ("Chicken wings", "lb", 3.0),
    "salmon": ("Salmon fillet", "lb", 10.0),
    "cod": ("Cod fillet", "lb", 6.0),
    "shrimp": ("Shrimp", "lb", 9.0),
    "calamari": ("Calamari", "lb", 5.0),
    "pasta": ("Dry pasta", "lb", 1.2),
    "quinoa": ("Quinoa", "lb", 3.0),
    "potato": ("Potato", "lb", 0.7),
    "cheddar": ("Cheddar", "lb", 4.5),
    "mozzarella": ("Mozzarella", "lb", 4.0),
    "parmesan": ("Parmesan", "lb", 9.0),
    "provolone": ("Provolone", "lb", 5.0),
    "cream": ("Heavy cream", "qt", 3.5),
    "butter": ("Butter", "lb", 4.2),
    "eggs": ("Eggs", "doz", 3.5),
    "flour": ("Flour", "lb", 0.6),
    "sugar": ("Sugar", "lb", 0.8),
    "romaine": ("Romaine", "head", 1.5),
    "mixed_greens": ("Mixed greens", "lb", 3.5),
    "tomato": ("Tomato", "lb", 1.6),
    "onion": ("Onion", "lb", 0.8),
    "bun": ("Burger bun", "each", 0.45),
    "veggie_patty": ("Veggie patty", "each", 1.6),
    "tortilla_chips": ("Tortilla chips", "lb", 2.5),
    "soup_base": ("Soup base", "qt", 1.8),
    "cream_cheese": ("Cream cheese", "lb", 3.0),
    "graham": ("Graham crackers", "lb", 2.0),
    "ice_cream": ("Vanilla ice cream", "qt", 4.0),
    "chocolate": ("Chocolate", "lb", 4.0),
    "lime": ("Lime", "each", 0.2),
    "oil": ("Cooking oil", "gal", 9.0),
    "tomato_sauce": ("Tomato sauce", "qt", 2.5),
    "garlic": ("Garlic", "lb", 2.5),
    "lemon": ("Lemon", "each", 0.3),
    "hot_sauce": ("Wing sauce", "qt", 4.0),
    "soda_syrup": ("Soda syrup", "gal", 14.0),
    "draft_beer": ("Draft beer", "oz", 0.08),
    "house_wine": ("House wine", "oz", 0.35),
}

# item_id: (name, category, base_price, base weekly units, {ingredient: qty per serving})
ITEMS = {
    "wings": ("Wings", "Starters", 13.0, 100, {"chicken_wings": 1.0, "hot_sauce": 0.06, "oil": 0.01}),
    "calamari": ("Fried Calamari", "Starters", 14.0, 45, {"calamari": 0.5, "flour": 0.1, "oil": 0.02, "lemon": 0.5, "tomato_sauce": 0.05}),
    "nachos": ("Loaded Nachos", "Starters", 13.0, 90, {"tortilla_chips": 0.4, "cheddar": 0.3, "tomato": 0.15, "onion": 0.1, "hot_sauce": 0.03}),
    "soup": ("Soup of the Day", "Starters", 8.0, 60, {"soup_base": 0.4, "cream": 0.1, "onion": 0.15, "butter": 0.03}),
    "caesar": ("Caesar Salad", "Starters", 11.0, 30, {"romaine": 1.0, "parmesan": 0.1, "oil": 0.01, "garlic": 0.02, "eggs": 0.05}),
    "classic_burger": ("Classic Burger", "Burgers and sandwiches", 15.0, 140, {"ground_beef": 0.5, "bun": 1, "cheddar": 0.06, "tomato": 0.1, "onion": 0.05}),
    "bacon_burger": ("Bacon Cheeseburger", "Burgers and sandwiches", 17.0, 110, {"ground_beef": 0.5, "bun": 1, "cheddar": 0.1, "bacon": 0.08, "tomato": 0.1}),
    "veggie_burger": ("Veggie Burger", "Burgers and sandwiches", 14.0, 35, {"veggie_patty": 1, "bun": 1, "mixed_greens": 0.05, "tomato": 0.1, "provolone": 0.1}),
    "chicken_sandwich": ("Chicken Sandwich", "Burgers and sandwiches", 14.0, 85, {"chicken_breast": 0.45, "bun": 1, "flour": 0.1, "oil": 0.02, "tomato": 0.08}),
    "philly": ("Philly Cheesesteak", "Burgers and sandwiches", 16.0, 50, {"shaved_beef": 0.35, "bun": 1, "provolone": 0.1, "onion": 0.1}),
    "ribeye": ("Ribeye", "Entrees", 38.0, 38, {"ribeye": 0.625, "potato": 0.4, "butter": 0.06, "mixed_greens": 0.1}),
    "sirloin": ("Sirloin", "Entrees", 28.0, 38, {"sirloin": 0.625, "potato": 0.4, "butter": 0.05, "mixed_greens": 0.1}),
    "salmon": ("Salmon", "Entrees", 27.0, 45, {"salmon": 0.5, "quinoa": 0.15, "lemon": 0.5, "butter": 0.04, "mixed_greens": 0.1}),
    "chicken_parm": ("Chicken Parm", "Entrees", 22.0, 110, {"chicken_breast": 0.6, "mozzarella": 0.15, "pasta": 0.3, "tomato_sauce": 0.1, "flour": 0.08}),
    "short_rib": ("Short Rib", "Entrees", 31.0, 35, {"short_rib": 0.75, "potato": 0.4, "cream": 0.05, "onion": 0.1}),
    "mac_cheese": ("Mac and Cheese", "Entrees", 16.0, 35, {"pasta": 0.4, "cheddar": 0.3, "cream": 0.1, "butter": 0.04}),
    "fish_chips": ("Fish and Chips", "Entrees", 20.0, 90, {"cod": 0.5, "potato": 0.5, "flour": 0.15, "oil": 0.03, "lemon": 0.5}),
    "bolognese": ("Spaghetti Bolognese", "Pasta and bowls", 19.0, 70, {"pasta": 0.4, "ground_beef": 0.3, "tomato_sauce": 0.15, "onion": 0.1, "parmesan": 0.05}),
    "scampi": ("Shrimp Scampi", "Pasta and bowls", 24.0, 35, {"pasta": 0.4, "shrimp": 0.45, "butter": 0.08, "garlic": 0.04, "lemon": 0.5}),
    "alfredo": ("Chicken Alfredo", "Pasta and bowls", 20.0, 75, {"pasta": 0.4, "chicken_breast": 0.4, "cream": 0.2, "parmesan": 0.1, "butter": 0.04}),
    "grain_bowl": ("Grain Bowl", "Pasta and bowls", 16.0, 30, {"quinoa": 0.3, "mixed_greens": 0.15, "tomato": 0.15, "chicken_breast": 0.25, "oil": 0.01}),
    "cheesecake": ("Cheesecake", "Desserts", 9.0, 30, {"cream_cheese": 0.3, "graham": 0.1, "sugar": 0.1, "eggs": 0.1}),
    "sundae": ("Brownie Sundae", "Desserts", 9.0, 55, {"chocolate": 0.15, "ice_cream": 0.12, "flour": 0.1, "sugar": 0.1, "butter": 0.05}),
    "key_lime": ("Key Lime Pie", "Desserts", 8.0, 25, {"lime": 3, "graham": 0.1, "sugar": 0.1, "cream": 0.1, "eggs": 0.1}),
    "churros": ("Churros", "Desserts", 8.0, 35, {"flour": 0.3, "sugar": 0.15, "oil": 0.04, "chocolate": 0.1, "eggs": 0.1}),
    "fries": ("Fries", "Drinks and sides", 6.0, 190, {"potato": 0.9, "oil": 0.06}),
    "side_salad": ("Side Salad", "Drinks and sides", 6.0, 40, {"mixed_greens": 0.2, "tomato": 0.1, "onion": 0.03}),
    "soda": ("Soda", "Drinks and sides", 3.5, 160, {"soda_syrup": 0.05}),
    "beer": ("Draft Beer", "Drinks and sides", 7.0, 150, {"draft_beer": 16}),
    "wine": ("House Wine", "Drinks and sides", 9.0, 90, {"house_wine": 6}),
}

# Authored truth: category mean own-price elasticity, each item jittered by +/-0.25.
CATEGORY_ELASTICITY = {
    "Drinks and sides": -0.4,
    "Starters": -0.8,
    "Burgers and sandwiches": -0.9,
    "Pasta and bowls": -1.0,
    "Desserts": -1.1,
    "Entrees": -1.4,
}
CROSS_CATEGORY_SHARE = 0.10
NB_DISPERSION = 40.0

# Mid-year rises (item_id: (week index it takes effect, multiplier)) and short promos.
PRICE_RISES = {
    "classic_burger": (26, 1.06),
    "salmon": (28, 1.05),
    "chicken_parm": (24, 1.07),
    "fries": (30, 1.08),
    "beer": (27, 1.07),
}
PROMOS = [  # (item_id, first week, last week, price multiplier)
    ("wings", 14, 15, 0.85),
    ("cheesecake", 38, 39, 0.80),
]
HOLIDAY_DIP = {46: 0.85, 51: 0.80}  # Thanksgiving and Christmas weeks

SUMMER_ITEMS = {"Drinks and sides": 0.25, "Starters": 0.08}
WINTER_ITEMS = {"soup": 0.30, "mac_cheese": 0.15, "short_rib": 0.15, "bolognese": 0.08}


def week_starts() -> pd.DatetimeIndex:
    return pd.date_range(FIRST_WEEK, periods=N_WEEKS, freq="7D")


def build_tables(rng: np.random.Generator) -> dict[str, pd.DataFrame]:
    menu_items = pd.DataFrame(
        [(i, v[0], v[1], v[2]) for i, v in ITEMS.items()],
        columns=["item_id", "name", "category", "base_price"],
    )
    ingredients = pd.DataFrame(
        [(i, v[0], v[1]) for i, v in INGREDIENTS.items()],
        columns=["ingredient_id", "name", "unit"],
    )
    recipes = pd.DataFrame(
        [(i, ing, q) for i, v in ITEMS.items() for ing, q in v[4].items()],
        columns=["item_id", "ingredient_id", "qty_per_serving"],
    )
    return {"menu_items": menu_items, "ingredients": ingredients, "recipes": recipes}


def build_ingredient_costs(rng: np.random.Generator, weeks: pd.DatetimeIndex) -> pd.DataFrame:
    rows = []
    for ing, (_, _, start) in INGREDIENTS.items():
        sd = 0.035 if ing in {"ribeye", "sirloin", "short_rib", "ground_beef", "shaved_beef"} else 0.02
        cost = start * COST_SCALE
        for w in range(0, N_WEEKS, 4):
            if w > 0:
                cost *= float(np.exp(rng.normal(0.002, sd)))
            rows.append((ing, weeks[w].strftime("%Y-%m-%d"), round(cost, 4)))
    return pd.DataFrame(rows, columns=["ingredient_id", "effective_week", "unit_cost"])


def build_ground_truth(rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for item_id, (_, category, *_rest) in ITEMS.items():
        eps = CATEGORY_ELASTICITY[category] + float(rng.uniform(-0.25, 0.25))
        rows.append(
            (
                item_id,
                category,
                round(eps, 3),
                round(float(rng.uniform(0.30, 0.50)), 3),
                CROSS_CATEGORY_SHARE,
            )
        )
    return pd.DataFrame(
        rows,
        columns=["item_id", "category", "true_elasticity", "within_category_switch_share", "cross_category_switch_share"],
    )


def price_path(item_id: str, weeks: pd.DatetimeIndex) -> np.ndarray:
    base = ITEMS[item_id][2]
    p = np.full(N_WEEKS, base)
    if item_id in PRICE_RISES:
        start, mult = PRICE_RISES[item_id]
        p[start:] = round(base * mult * 2) / 2  # menu prices move in $0.50 steps
    for pid, first, last, mult in PROMOS:
        if pid == item_id:
            p[first : last + 1] = np.round(p[first : last + 1] * mult, 2)
    return p


def seasonal_factor(item_id: str, category: str, w: int) -> float:
    summer = 0.5 * (1 + np.cos(2 * np.pi * (w - 28) / 52))
    winter = 1 - summer
    f = 1 + SUMMER_ITEMS.get(category, 0.0) * (summer - 0.5) * 2
    f *= 1 + WINTER_ITEMS.get(item_id, 0.0) * (winter - 0.5) * 2
    return f * HOLIDAY_DIP.get(w, 1.0)


def build_weekly_sales(rng: np.random.Generator, weeks: pd.DatetimeIndex, truth: pd.DataFrame) -> pd.DataFrame:
    ids = list(ITEMS)
    n = len(ids)
    cats = np.array([ITEMS[i][1] for i in ids])
    base = np.array([ITEMS[i][3] for i in ids], dtype=float)
    base_price = np.array([ITEMS[i][2] for i in ids])
    t = truth.set_index("item_id").loc[ids]
    eps = t["true_elasticity"].to_numpy()
    within = t["within_category_switch_share"].to_numpy()
    cross = t["cross_category_switch_share"].to_numpy()
    prices = np.column_stack([price_path(i, weeks) for i in ids])  # (weeks, items)
    trend = rng.normal(0.0, 0.0008, size=n)

    same = cats[:, None] == cats[None, :]
    rows = []
    for w in range(N_WEEKS):
        level = np.array(
            [base[k] * seasonal_factor(ids[k], cats[k], w) * (1 + trend[k]) ** w for k in range(n)]
        )
        ratio = prices[w] / base_price
        own = level * ratio**eps
        lost = level - own  # negative on a price cut: the item pulls buyers in
        inflow = np.zeros(n)
        for j in range(n):
            if lost[j] == 0:
                continue
            in_cat = same[j] & (np.arange(n) != j)
            out_cat = ~same[j]
            w_in = level * in_cat
            w_out = level * out_cat
            inflow += lost[j] * within[j] * w_in / w_in.sum()
            inflow += lost[j] * cross[j] * w_out / w_out.sum()
        mu = np.maximum(own + inflow, 1.0)
        p = NB_DISPERSION / (NB_DISPERSION + mu)
        units = rng.negative_binomial(NB_DISPERSION, p)
        for k in range(n):
            rows.append((weeks[w].strftime("%Y-%m-%d"), ids[k], int(units[k]), float(prices[w, k])))
    return pd.DataFrame(rows, columns=["week_start", "item_id", "units_sold", "avg_selling_price"])


def counterfactual_daily_units(
    rng: np.random.Generator,
    base_daily: float,
    ratio_today: np.ndarray,
    ratio_yesterday: np.ndarray,
    elasticity: float,
    carryover: float = 0.5,
    dispersion: float = NB_DISPERSION / 7,
) -> np.ndarray:
    """Authored counterfactual demand for simulated switchback tests (validation only).

    Daily units for one item given its price ratio today and yesterday: the price effect is
    a mix of today's price (weight 1 - carryover) and yesterday's (weight `carryover`), so a
    block right after a switch is only partly clean. Daily noise is negative binomial with
    dispersion NB_DISPERSION / 7, so seven days sum to the weekly noise the generator uses.
    """
    log_r = (1 - carryover) * np.log(ratio_today) + carryover * np.log(ratio_yesterday)
    mu = base_daily * np.exp(elasticity * log_r)
    return rng.negative_binomial(dispersion, dispersion / (dispersion + mu))


def generate(out_dir: Path = OUT_DIR, seed: int = SEED) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    weeks = week_starts()
    tables = build_tables(rng)
    tables["ingredient_costs"] = build_ingredient_costs(rng, weeks)
    truth = build_ground_truth(rng)
    tables["weekly_sales"] = build_weekly_sales(rng, weeks, truth)
    tables["ground_truth"] = truth
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_csv(out_dir / f"{name}.csv", index=False, float_format="%.4f", lineterminator="\n")
    return tables


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()
    tables = generate(args.out, args.seed)
    for name, df in tables.items():
        print(f"{name:18s} {len(df):5d} rows")
