-- Raw tables mirror the five synthetic CSVs one to one.
-- Ground truth lives in its own schema; only sim/validation.py may read it.

CREATE TABLE raw_menu_items (
    item_id    VARCHAR PRIMARY KEY,
    name       VARCHAR NOT NULL,
    category   VARCHAR NOT NULL,
    base_price DOUBLE  NOT NULL
);

CREATE TABLE raw_ingredients (
    ingredient_id VARCHAR PRIMARY KEY,
    name          VARCHAR NOT NULL,
    unit          VARCHAR NOT NULL
);

CREATE TABLE raw_recipes (
    item_id         VARCHAR NOT NULL,
    ingredient_id   VARCHAR NOT NULL,
    qty_per_serving DOUBLE  NOT NULL,
    PRIMARY KEY (item_id, ingredient_id)
);

CREATE TABLE raw_ingredient_costs (
    ingredient_id  VARCHAR NOT NULL,
    effective_week DATE    NOT NULL,
    unit_cost      DOUBLE  NOT NULL,
    PRIMARY KEY (ingredient_id, effective_week)
);

CREATE TABLE raw_weekly_sales (
    week_start        DATE    NOT NULL,
    item_id           VARCHAR NOT NULL,
    units_sold        INTEGER NOT NULL,
    avg_selling_price DOUBLE  NOT NULL,
    PRIMARY KEY (week_start, item_id)
);

-- Parameters read by the views. One row; editable defaults, all assumptions.
CREATE TABLE config (
    window_weeks      INTEGER NOT NULL,  -- trailing baseline window
    min_units         INTEGER NOT NULL,  -- below this over the window: insufficient data
    popularity_factor DOUBLE  NOT NULL   -- popular if share >= factor / N
);
INSERT INTO config VALUES (12, 50, 0.7);

CREATE SCHEMA validation;

CREATE TABLE validation.ground_truth (
    item_id                      VARCHAR PRIMARY KEY,
    category                     VARCHAR NOT NULL,
    true_elasticity              DOUBLE  NOT NULL,
    within_category_switch_share DOUBLE  NOT NULL,
    cross_category_switch_share  DOUBLE  NOT NULL
);
