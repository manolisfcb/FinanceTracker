import pandas as pd
from app import db
from src.models import StockModel
from src.models import PortfolioModel
from src.models import UserModel
from app import app


positions = pd.read_excel('posicao.xlsx')

print(positions.head())



def portfolio():
    with app.app_context():  # Ensure the app context is active
        # Remove all existing tickets
        db.session.query(PortfolioModel).delete()
        for index, row in positions.iterrows():
            user = UserModel.query.filter_by(email=row['email']).first()
            stock = StockModel.query.filter_by(symbol=row['symbol']).first()
            if user and stock:
                portfolio = PortfolioModel(
                    user_id=4,
                    stock_id=stock.id,
                    avg_price=row['avg_price'],
                    actual_price=row['actual_price'],
                    adquisition_cost=row['adquisition_cost'],
                    quantity=row['quantity'],
                    profit=row['profit'],
                    percent_return=row['percent_return'],
                    dividend_amount=row['dividend_amount']
                )
                db.session.add(portfolio)
        db.session.commit()
        print("Test data generated successfully!")