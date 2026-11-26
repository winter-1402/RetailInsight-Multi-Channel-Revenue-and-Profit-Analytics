WITH buyers AS (
    SELECT party_id, channel, SUM(revenue_units) AS revenue_units
    FROM sales GROUP BY party_id, channel
)
SELECT channel,
       CASE WHEN revenue_units >= 10000000 THEN '1000_USD_plus'
            WHEN revenue_units >= 2000000 THEN '200_to_1000_USD'
            ELSE 'under_200_USD' END AS segment,
       COUNT(*) AS buyers, SUM(revenue_units) AS revenue_units
FROM buyers GROUP BY 1, 2 ORDER BY channel NULLS LAST, segment NULLS LAST
