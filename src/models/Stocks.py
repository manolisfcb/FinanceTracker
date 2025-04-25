from flask_sqlalchemy import SQLAlchemy
from enum import Enum
from sqlalchemy.orm import relationship
from app import db
from .Orders import OrderModel


class StockModel(db.Model):
    __tablename__ = 'stocks'
    
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
    
    previous_close = db.Column(db.Float, nullable=True)
    dividend_yield = db.Column(db.Float, nullable=True)
    ex_dividend_date = db.Column(db.String(100), nullable=True)
    current_price = db.Column(db.Float, nullable=True)
    fiftyTwoWeekHigh = db.Column(db.Float, nullable=True)
    
    
        
    def __repr__(self):
        return f"<StockModel(symbol={self.symbol}, quantity={self.quantity}, price={self.price})>"
    
    def serialize(self):
        return {
            "id": self.id,
            "symbol": self.symbol,
            "root_symbol": self.root_symbol,
            "cvm_code": self.cvm_code,
            "sector": self.sector,
            "industry": self.industry,
            "country": self.country,
            "long_name": self.long_name,
            "short_name": self.short_name,
            "website": self.website,
            "floatShares": self.floatShares,
            "previous_close": self.previous_close,
            "dividend_yield": self.dividend_yield,
            "ex_dividend_date": self.ex_dividend_date,
            "current_price": self.current_price,
            "fiftyTwoWeekHigh": self.fiftyTwoWeekHigh,
            
            
            
        }

    def save(self):
        db.session.add(self)
        db.session.commit()