from flask_sqlalchemy import SQLAlchemy
from enum import Enum
from sqlalchemy.orm import relationship
from app import db
from .Orders import OrderModel


class StockModel(db.Model):
    __tablename__ = 'stocks'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    symbol = db.Column(db.String(10),  nullable=False)# Asignar nombre a la FK
    root_symbol = db.Column(db.String(6), nullable=True)
    long_name = db.Column(db.String(100), nullable=True)
    short_name = db.Column(db.String(10), nullable=True)
    website = db.Column(db.String(100), nullable=True)
    cvm_code = db.Column(db.Integer, nullable=True)
    quantity = db.Column(db.Integer, nullable=False)
    sector = db.Column(db.String(100), nullable=True)
    industry = db.Column(db.String(100), nullable=True)
    country = db.Column(db.String(100), nullable=True)
    
    user = db.relationship('UserModel', backref='stocks', lazy=True)
    
    def __repr__(self):
        return f"<StockModel(symbol={self.symbol}, quantity={self.quantity}, price={self.price})>"
    
    def serialize(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "symbol": self.symbol,
            "root_symbol": self.root_symbol,
            "cvm_code": self.cvm_code,
            "quantity": self.quantity,
            "sector": self.sector,
            "industry": self.industry,
            "country": self.country,
            "long_name": self.long_name,
            "short_name": self.short_name,
            "website": self.website
            
            
        }
    
    def get_averages_stock_price(user_id, symbol):
        return StockModel.query.filter_by(user_id=user_id, symbol=symbol).with_entities(db.func.avg(StockModel.price)).scalar() or 0.0
    
    def get_adquisition_cost(user_id):
        return StockModel.query.filter_by(user_id=user_id).with_entities(db.func.sum(StockModel.price)).scalar() or 0.0
    
    