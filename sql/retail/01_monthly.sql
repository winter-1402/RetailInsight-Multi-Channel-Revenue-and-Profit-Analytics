SELECT purchase_month, channel, SUM(revenue_units) AS revenue_units,
       SUM(cost_units) AS cost_units, SUM(profit_units) AS profit_units,
       COUNT(DISTINCT order_id) AS orders
FROM sales GROUP BY purchase_month, channel ORDER BY purchase_month NULLS LAST, channel NULLS LAST
