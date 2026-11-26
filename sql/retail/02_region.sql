SELECT region, channel, SUM(revenue_units) AS revenue_units,
       SUM(cost_units) AS cost_units, SUM(profit_units) AS profit_units,
       COUNT(DISTINCT order_id) AS orders
FROM sales GROUP BY region, channel ORDER BY region NULLS LAST, channel NULLS LAST
