
# This query will group by user_id and symbol, and will return the average price of the stock
PORTFOLIO = f"""
SELECT
    user_id,
    symbol AS name,
    -- Volume-weighted average (instead of raw AVG)
    SUM(price * quantity) * 1.0 / SUM(quantity) AS avg_price,

    SUM(quantity) AS quantity,
    SUM(price * quantity) AS cost,
    
    -- Example "profit" and "percent_return" placeholders
    -- (It depends on what you'd like them to represent!)
    0 AS profit,
    0 AS percent_return,

    0 AS dividend_amount
FROM stocks
GROUP BY user_id, symbol;

"""
