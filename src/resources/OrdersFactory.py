from abc import ABC, abstractmethod 
import pandas as pd
from src.models import StockModel

class OrdersStrategy(ABC):
    @abstractmethod
    def create_orders(self):
        pass
    

class OrdersFromB3(OrdersStrategy):
    def create_orders(self, orders: pd.DataFrame):
        
        orders['Data do Negócio'] = orders['Data do Negócio'].apply(self.get_date)
        orders['Tipo de Movimentação'] = orders['Tipo de Movimentação'].apply(self.check_negotiation_type)
        orders['Código de Negociação'] = orders['Código de Negociação'].apply(self.adjust_stock_symbol)
        orders['stock_id'] = orders['Código de Negociação'].apply(self.check_stock_exists)
        orders.rename(columns={'Preço': 'price', 'Quantidade': 'quantity', 'Data do Negócio': 'date', 'Tipo de Movimentação': 'type'}, inplace=True)
        orders.drop(columns=['Prazo/Vencimento', 'Valor', 'Instituição',  'Mercado', 'Código de Negociação'], inplace=True)    

        return orders
        
    def adjust_stock_symbol(self, symbol):
        if symbol.endswith('F'):
            return symbol[:-1] + '.SA'
        return symbol + '.SA'
    
    def check_stock_exists(self, symbol):
        try:
            stock_id = StockModel.query.filter_by(symbol=symbol).first().id
            return stock_id
        except:
            print(f"Stock {symbol} not found")
            return symbol
        
    def check_negotiation_type(self, type_of_negotiation):
        if type_of_negotiation == 'Compra':
            return 'BUY'
        return 'SELL'
    
    def get_date(self, date):
        return pd.to_datetime(date, format='%d/%m/%Y')
    
class Orders(OrdersStrategy):
    def __init__(self, strategy: OrdersStrategy, orders: pd.DataFrame):
        self.strategy = strategy
        self.orders_df = orders
        
    def create_orders(self):
        return self.strategy.create_orders(self.orders_df)