
from sqlalchemy import text
# This query will group by user_id and symbol, and will return the average price of the stock
def get_portfolio(user_id: int):

    PORTFOLIO = text(f"""
    SELECT
    st.root_symbol,
    st.symbol,
    pt.actual_price,
    pt.quantity,
    pt.adquisition_cost,
    pt.avg_price,
    pt.profit,
    pt.percent_return,
    0 as percent_return_dividends
    FROM portfolios pt 
    JOIN stocks st ON pt.stock_id = st.id
    WHERE
    pt.user_id = {user_id}
    """)
    return PORTFOLIO