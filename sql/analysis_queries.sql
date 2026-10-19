-- Business queries run by etl/run_queries.py. Each block starts with "-- name: <name>".

-- name: item_contribution
SELECT item_id, name, category, price, ROUND(unit_cost, 2) AS unit_cost, ROUND(cm, 2) AS cm,
       ROUND(food_cost_pct * 100, 1) AS food_cost_pct, window_units,
       ROUND(weekly_contribution_profit, 0) AS weekly_contribution_profit
FROM v_item_cm
ORDER BY weekly_contribution_profit DESC;

-- name: category_summary
SELECT category, COUNT(*) AS items, SUM(window_units) AS window_units,
       ROUND(SUM(weekly_contribution_profit), 0) AS weekly_contribution_profit,
       ROUND(SUM(weekly_contribution_profit) / (SUM(weekly_units * price)) * 100, 1) AS contribution_margin_pct
FROM v_item_cm
GROUP BY category
ORDER BY weekly_contribution_profit DESC;

-- name: matrix_by_category
SELECT scope_key AS category, name,
       ROUND(unit_share * 100, 1) AS share_pct,
       ROUND(cm, 2) AS cm,
       ROUND(margin_threshold, 2) AS margin_threshold,
       CASE WHEN insufficient_data = 1 THEN 'Insufficient data'
            WHEN unit_share >= popularity_threshold AND cm >= margin_threshold THEN 'Star'
            WHEN unit_share >= popularity_threshold THEN 'Plowhorse'
            WHEN cm >= margin_threshold THEN 'Puzzle'
            ELSE 'Dog' END AS class
FROM v_matrix_inputs
WHERE scope = 'category'
ORDER BY category, cm DESC;

-- name: beef_exposure
SELECT m.name, m.category,
       ROUND(SUM(CASE WHEN r.ingredient_id IN ('ribeye','sirloin','short_rib','ground_beef','shaved_beef')
                      THEN r.qty_per_serving * c.unit_cost ELSE 0 END), 2) AS beef_cost,
       ROUND(SUM(r.qty_per_serving * c.unit_cost), 2) AS unit_cost
FROM raw_menu_items m
JOIN raw_recipes r ON r.item_id = m.item_id
JOIN v_latest_ingredient_cost c ON c.ingredient_id = r.ingredient_id
GROUP BY m.name, m.category
HAVING SUM(CASE WHEN r.ingredient_id IN ('ribeye','sirloin','short_rib','ground_beef','shaved_beef')
                THEN 1 ELSE 0 END) > 0
ORDER BY beef_cost DESC;

-- name: ingredient_cost_trend
SELECT ingredient_id, MIN(unit_cost) AS min_cost, MAX(unit_cost) AS max_cost,
       ROUND((MAX(unit_cost) - MIN(unit_cost)) / MIN(unit_cost) * 100, 1) AS range_pct
FROM raw_ingredient_costs
GROUP BY ingredient_id
ORDER BY range_pct DESC
LIMIT 10;
