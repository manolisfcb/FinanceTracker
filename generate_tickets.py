import random
from faker import Faker
from app import app, db
import pandas as pd
from src.models import UserModel, TransactionModel, Category, TicketModel
import datetime
fake = Faker()

def generate_transactions():
    with app.app_context():  # Ensure the app context is active
        stocks = pd.read_csv('TicketModel.csv')
        """     
            id = db.Column(db.Integer, primary_key=True)
            symbol = db.Column(db.String(10), nullable=False)
            cvm_code = db.Column(db.String(10), nullable=True)      
            long_name = db.Column(db.String(100), nullable=False)
            short_name = db.Column(db.String(10), nullable=False)
            floatShares = db.Column(db.Integer, nullable=False)
            website = db.Column(db.String(100), nullable=True)
            sectorKey = db.Column(db.String(10), nullable=False)
            sector = db.Column(db.String(100), nullable=False)
            industry = db.Column(db.String(100), nullable=False)
            country = db.Column(db.String(100), nullable=False)
         """
         
        for index, row in stocks.iterrows():
            # existing_ticket = TicketModel.query.filter_by(symbol=row['symbol']).first()
            # if not existing_ticket:
            ticket = TicketModel(symbol=row['symbol'], 
                                    cvm_code=row['CVM_CODE'],
                                    long_name=row['long_name'], 
                                    short_name=row['short_name'], 
                                    floatShares=row['floatShares'], 
                                    website=row['website'], 
                                    sectorKey=row['sectorKey'], 
                                    sector=row['sector'], 
                                    industry=row['industry'], 
                                    country=row['country'])
            db.session.add(ticket)
        db.session.commit()
        

        print("Test data generated successfully!")

generate_transactions()