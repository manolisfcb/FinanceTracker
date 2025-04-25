from app import db, app, scheduler
import random
from src.models import StockModel
import yfinance as yf
import os
from concurrent.futures import ThreadPoolExecutor
from time import sleep

cores = os.cpu_count()

base_delay = 1
def get_info(symbol):
    stock = yf.Ticker(symbol)
    retry = 0
    while retry < 3:
        print(f"retry: {retry}")
        try:
            info = stock.get_info()
            break
        except:
            delay = random.randint(1, 3)
            sleep(delay)
            retry += 1
            if retry == 3:
                print(f"Failed to get price for {symbol}")
                info = None

    return info


@scheduler.task('interval', id='update_stocks_info', seconds=3600)  # Every hour
def update_stocks_info():
    """
    Periodically updates stock data in the database using yfinance.Ticker.
    """
    with scheduler.app.app_context():
        # Fetch all stocks from the database
        stocks = StockModel.query.all()
        symbols = [stock.symbol for stock in stocks]

        if not symbols:
            print("No stocks to update.")
            return

        # Fetch data concurrently using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=cores) as executor:
            results = executor.map(get_info, symbols)

        # Update stock information in the database
        for stock, info in zip(stocks, results):
            if info:
                print(f"Updating {stock.symbol}")
                stock.previous_close = info.get('previousClose', None)
                stock.current_price = info.get('currentPrice', None)
                stock.fiftyTwoWeekHigh = info.get('fiftyTwoWeekHigh', None)
                stock.save()

        print("Stocks updated successfully.")
