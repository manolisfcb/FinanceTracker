# USING TreadPoolExecutor to generate orders

import random

from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import yfinance as yf
from time import sleep

# Number of cores on your machine
import os
cores = os.cpu_count()


stocks = pd.read_csv('TicketModel.csv') 

symbols = stocks['symbol'].tolist() 


def get_info(symbol):
    stock = yf.Ticker(symbol)
    retry = 0
    while retry <3:
        print(f"retry: {retry}")
        try:
            price = int(stock.get_info()['currentPrice'])
            break
        except:
            sleep(2)
            retry += 1
            if retry == 3:
                print(f"Failed to get price for {symbol}")
        price = 0
    return {symbol: price}

with ThreadPoolExecutor(max_workers=cores-1) as executor:
    prices = executor.map(get_info, symbols)
    
prices = list(prices)
print(prices)