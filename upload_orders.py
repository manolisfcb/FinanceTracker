import pandas as pd

from app import db
from src.models import StockModel, OrderModel
from src.models import PortfolioModel
from src.models import UserModel
from app import app


orders = pd.read_excel('negociacao.xlsx')
fiis = ["KNRI11",
        "MXRF11",
        "HGLG11",
        "HGRE11",
        "HGBS",
        "VINO11",
        "VISC",
        "VRTA11",
        "DEVA11",
        "HFOF11",
        "KNCR11",
        "ALZR11",
        "XPML11",]

print(orders.columns)


def get_orders(orders):
    with app.app_context():  # Ensure the app context is active
        # Remove all existing tickets
        for index, row in orders.iterrows():
            simb = row['Código de Negociação']
            if simb in fiis:
                continue
            if simb.endswith('F'):
                simb = simb[:-1] + '.SA'
            else:
                simb += '.SA'
            user_id = 4
            try:
                stock_id = StockModel.query.filter_by(symbol=simb).first().id
            except:
                print(f"Stock {simb} not found")
                continue
            type_of_negotiation = row['Tipo de Movimentação']
            if type_of_negotiation == 'Compra':
                type_of_negotiation = 'BUY'
            else:
                type_of_negotiation = 'SELL'
            quantity = row['Quantidade']
            price = row['Preço']
            date = row['Data do Negócio']
            date = pd.to_datetime(date, format='%d/%m/%Y')
            order = OrderModel(
                user_id=user_id,
                stock_id=stock_id,
                type=type_of_negotiation,
                quantity=quantity,
                price=price,
                date=date
            )
            db.session.add(order)
        db.session.commit()
        print("Test data generated successfully!")

get_orders(orders)    
            