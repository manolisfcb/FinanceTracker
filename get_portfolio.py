from app import db, app
from src.models import PortfolioModel, UserModel, StockModel, OrderModel
import pandas as pd 
from sqlalchemy import text
from time import sleep
import yfinance as yf
import os
cores = os.cpu_count()
# from .get_stocks_info import get_info
from concurrent.futures import ThreadPoolExecutor
t = """
    SELECT a.*, b.* FROM orders a JOIN stocks b ON a.stock_id = b.id WHERE a.user_id = 4;
    """
def get_info(symbol):
    stock = yf.Ticker(symbol)
    retry = 0
    while retry <3:
        print(f"retry: {retry}")
        try:
            info = stock.get_info()
            break
        except:
            sleep(2)
            retry += 1
            if retry == 3:
                print(f"Failed to get price for {symbol}")
                info = None

    return info


def get_price(row):
    if row['type'] == 'BUY':
        return row['price']
    else:
        return -row['price']


def get_portfolio():
    
    """  
    #         'name': 'BBSE3',
    #         'price': 36.01,
    #         'quantity': 12,
    #         'value': 432.12,
    #         'cost': 371.718,
    #         'avg_price': 30.98,
    #         'profit': 108.25,
    #         'percent_return': '16.25%',
    #         'percent_return_dividends': '29.12%'
    """
    with app.app_context():
        user_id = 4
        orders = db.session.execute(
           text(t)
        )
        
        od_df = pd.DataFrame(orders.fetchall(), columns=orders.keys())
        symbols = od_df['symbol'].tolist()  
        
        with ThreadPoolExecutor(max_workers=cores-1) as executor:
            info = executor.map(get_info, symbols)
        info_df = pd.DataFrame(info)
        # for intel in info:
        
        full_df = pd.merge(od_df, info_df, left_on='symbol', right_on='symbol')
        
        average_price = od_df.groupby('symbol')['price'].mean()
        od_df['price'] = od_df.apply(get_price, axis=1)
        cost = od_df.groupby('symbol')['price'].sum()
        quantity = od_df.groupby('symbol')['quantity'].sum()
        



        print(cost)    
        print(average_price)
        
                
get_portfolio()
        
    # with app.app_context():
    #     user_id = 4
        
    #     # 1) Hacemos el JOIN entre OrderModel y StockModel
    #     #    y filtramos por OrderModel.user_id == 4
    #     results = (
    #         db.session.query(OrderModel, StockModel)
    #         .join(StockModel, OrderModel.stock_id == StockModel.id)
    #         .filter(OrderModel.user_id == user_id)
    #         .all()
    #     )
        
    #     # 2) 'results' será una lista de tuplas: [(OrderModel, StockModel), (OrderModel, StockModel), ...]
    #     #    Convertimos cada tupla en un diccionario para armar el DataFrame
    #     data = []
    #     for order, stock in results:
    #         data.append({
    #             "order_id": order.id,
    #             "user_id": order.user_id,
    #             "stock_id": order.stock_id,
    #             "quantity": order.quantity,
    #             # ... cualquier otro campo de OrderModel
    #             # "stock_name": stock.symbol,
    #             "stock_symbol": stock.symbol,
    #             # "stock_price": stock.price,
    #             # ... cualquier otro campo de StockModel
    #         })
        
    #     # 3) Creamos el DataFrame
    #     od_df = pd.DataFrame(data)
    #     print(od_df)