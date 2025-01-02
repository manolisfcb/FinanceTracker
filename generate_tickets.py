import random
from faker import Faker
from app import app, db
import pandas as pd
from src.models import UserModel, TransactionModel, Category, StockModel
import datetime
fake = Faker()

def generate_transactions():
    with app.app_context():  # Ensure the app context is active
        stocks = pd.read_csv('TicketModel.csv')
        """     
            id = db.Column(db.Integer, primary_key=True)
            symbol = db.Column(db.String(10),  nullable=False)# Asignar nombre a la FK
            root_symbol = db.Column(db.String(6), nullable=True)
            long_name = db.Column(db.String(100), nullable=True)
            short_name = db.Column(db.String(10), nullable=True)
            website = db.Column(db.String(100), nullable=True)
            cvm_code = db.Column(db.Integer, nullable=True)
            floatShares = db.Column(db.Integer, nullable=True)
            sector = db.Column(db.String(100), nullable=True)
            industry = db.Column(db.String(100), nullable=True)
            country = db.Column(db.String(100), nullable=True)

         """
         
        # Remove all existing tickets
        db.session.query(StockModel).delete()
         
        for index, row in stocks.iterrows():
            # existing_ticket = TicketModel.query.filter_by(symbol=row['symbol']).first()
            # if not existing_ticket:
            ticket = StockModel(
                symbol=row['symbol'],
                root_symbol=row['symbol'][0:4],
                long_name=row['long_name'],
                short_name=row['short_name'],
                website=row['website'],
                cvm_code=row['CVM_CODE'],
                floatShares=row['floatShares'],
                sector=row['sector'],
                industry=row['industry'],
                country=row['country']               
                
                )
            db.session.add(ticket)
        db.session.commit()
        

        print("Test data generated successfully!")

generate_transactions()

