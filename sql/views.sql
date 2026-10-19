-- Descriptive layer: item cost, contribution margin, trailing baseline and
-- the inputs to the menu engineering matrix. Classification itself is a pure
-- function in sim/. Nothing here touches the validation schema.

-- The trailing weeks that make up the baseline.
CREATE VIEW v_window_weeks AS
SELECT w.week_start
FROM (
    SELECT week_start, DENSE_RANK() OVER (ORDER BY week_start DESC) AS rk
    FROM (SELECT DISTINCT week_start FROM raw_weekly_sales) d
) w
CROSS JOIN config c
WHERE w.rk <= c.window_weeks;

-- Most recent unit cost of each ingredient.
CREATE VIEW v_latest_ingredient_cost AS
SELECT ingredient_id, unit_cost
FROM (
    SELECT ingredient_id, unit_cost,
           ROW_NUMBER() OVER (PARTITION BY ingredient_id ORDER BY effective_week DESC) AS rn
    FROM raw_ingredient_costs
) t
WHERE rn = 1;

-- Plate cost of one serving: recipe quantities x latest ingredient cost.
CREATE VIEW v_item_cost AS
SELECT r.item_id, SUM(r.qty_per_serving * c.unit_cost) AS unit_cost
FROM raw_recipes r
JOIN v_latest_ingredient_cost c ON c.ingredient_id = r.ingredient_id
GROUP BY r.item_id;

-- Trailing-window units and the latest selling price per item.
CREATE VIEW v_item_baseline AS
SELECT s.item_id,
       SUM(s.units_sold) AS window_units,
       SUM(s.units_sold) * 1.0 / MAX(c.window_weeks) AS weekly_units,
       MAX(CASE WHEN s.week_start = (SELECT MAX(week_start) FROM v_window_weeks)
                THEN s.avg_selling_price END) AS price
FROM raw_weekly_sales s
JOIN v_window_weeks w ON w.week_start = s.week_start
CROSS JOIN config c
GROUP BY s.item_id;

-- One row per item: price, cost, contribution margin, baseline volume.
CREATE VIEW v_item_cm AS
SELECT m.item_id, m.name, m.category,
       b.price,
       k.unit_cost,
       b.price - k.unit_cost AS cm,
       k.unit_cost / b.price AS food_cost_pct,
       b.window_units,
       b.weekly_units,
       b.weekly_units * (b.price - k.unit_cost) AS weekly_contribution_profit,
       CASE WHEN b.window_units < c.min_units THEN 1 ELSE 0 END AS insufficient_data
FROM raw_menu_items m
JOIN v_item_baseline b ON b.item_id = m.item_id
JOIN v_item_cost k ON k.item_id = m.item_id
CROSS JOIN config c;

-- Matrix inputs for one scope. Insufficient-data items get no share and are
-- excluded from N and from the thresholds.
CREATE VIEW v_matrix_inputs AS
SELECT x.scope, x.scope_key, x.item_id, x.name, x.category,
       x.price, x.unit_cost, x.cm, x.food_cost_pct, x.window_units, x.insufficient_data,
       CASE WHEN x.insufficient_data = 1 THEN NULL
            ELSE x.window_units * 1.0 / SUM(x.classifiable_units) OVER (PARTITION BY x.scope, x.scope_key) END AS unit_share,
       CASE WHEN x.insufficient_data = 1 THEN NULL
            ELSE c.popularity_factor / SUM(x.classifiable) OVER (PARTITION BY x.scope, x.scope_key) END AS popularity_threshold,
       CASE WHEN x.insufficient_data = 1 THEN NULL
            ELSE SUM(x.classifiable_units * x.cm) OVER (PARTITION BY x.scope, x.scope_key)
                 / SUM(x.classifiable_units) OVER (PARTITION BY x.scope, x.scope_key) END AS margin_threshold
FROM (
    SELECT 'category' AS scope, category AS scope_key, i.*,
           CASE WHEN insufficient_data = 0 THEN 1 ELSE 0 END AS classifiable,
           CASE WHEN insufficient_data = 0 THEN window_units ELSE 0 END AS classifiable_units
    FROM v_item_cm i
    UNION ALL
    SELECT 'menu' AS scope, 'menu' AS scope_key, i.*,
           CASE WHEN insufficient_data = 0 THEN 1 ELSE 0 END AS classifiable,
           CASE WHEN insufficient_data = 0 THEN window_units ELSE 0 END AS classifiable_units
    FROM v_item_cm i
) x
CROSS JOIN config c;
