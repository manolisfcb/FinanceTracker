from abc import ABC, abstractmethod
import pandas as pd
# Strategy interface
class PortfolioStrategy(ABC):
    @abstractmethod
    def create_portfolio(self, data, user_id):
        pass


# Concrete strategy for Upload by Transaction

class PortfolioByTransaction(PortfolioStrategy):
    def create_portfolio(self, data: pd.DataFrame, user_id):
        
        # First, we need to group the data by symbol
        data_grouped = data.groupby('asset_id')
        average_price = data_grouped['price'].mean()
        quantity = data_grouped.apply(self._get_actual_quantity)
        total_cost = data_grouped.apply(self._get_total_cost)

        new_df = pd.DataFrame({'asset_id': average_price.index, 'avg_price': average_price.values, 'quantity': quantity.values, 'adquisition_cost': total_cost.values})
        new_df = new_df[new_df['quantity'] > 0]
        new_df['user_id'] = user_id
        new_df['dividend_amount'] = 0
        new_df['actual_price'] = new_df['asset_id'].apply(self._get_actual_price)
        new_df['current_cost'] = new_df['actual_price'] * new_df['quantity']
        new_df['profit'] = new_df['current_cost'] - new_df['adquisition_cost']
        new_df['percent_return'] = (new_df['profit'] / new_df['adquisition_cost']) * 100
        new_df['percent_return'] = new_df['percent_return'].apply(lambda x: round(x, 2))
  
        return new_df

    def _get_average_price(data):
        return data.groupby('symbol').agg({'price': 'mean'}).reset_index()

    def _get_date(row):
        date = row["Data do Negócio"]
        return pd.to_datetime(date, format='%d/%m/%Y')

    def _get_total_cost(self, data):
        # Calculate total cost for BUY and SELL directly
        data['total'] = data['price'] * data['quantity']
        
        # Aggregate total cost by type
        summary = data.groupby('type')['total'].sum()
        
        # Extract BUY and SELL totals, defaulting to 0 if absent
        total_buy_cost = summary.get('BUY', 0)
        total_sell_cost = summary.get('SELL', 0)
        
        return total_buy_cost - total_sell_cost
    
    def _get_actual_quantity(self, data):
        # Aggregate quantity by type
        summary = data.groupby('type')['quantity'].sum()
        
        # Extract BUY and SELL quantities, defaulting to 0 if absent
        total_buy_quantity = summary.get('BUY', 0)
        total_sell_quantity = summary.get('SELL', 0)
        
        return total_buy_quantity - total_sell_quantity
        
    def _get_actual_price(self, symbol_id):
        from src.models import Fundamentals

        try:
            latest = (
                Fundamentals.query.filter_by(asset_id=symbol_id)
                .order_by(Fundamentals.as_of_date.desc())
                .first()
            )
            return latest.price if latest else None
        except:
            return None
        
        
    def _get_type_of_negotiation(row):
        if row["Tipo de Movimentação"] == "Compra":
            return "BUY"
        return "SELL"
        
    def _get_symbol(row):
        return row['Código de Negociação']


# Concrete strategy for Upload by Position

class PortfolioByPosition(PortfolioStrategy):
    def create_portfolio(self, data, user_id):
        data['user_id'] = user_id
        data.rename(columns={'Preço de Fechamento': 'actual_price', 'Quantidade': 'quantity', 'Data do Negócio': 'negociation_date', 'Tipo de Movimentação': 'type_of_negotiation', 'Código de Negociação': 'symbol'}, inplace=True)
    
    
# Context class

class Portfolio:
    def __init__(self, strategy: PortfolioStrategy, data: pd.DataFrame, user_id: int):
        self.strategy = strategy
        self.portfolio_df = strategy.create_portfolio(data, user_id)
        
    def create_portfolio(self, data, user_id):
        return self.strategy.create_portfolio(data, user_id)
    
    def set_strategy(self, strategy):
        self.strategy = strategy
    