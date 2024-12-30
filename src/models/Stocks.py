from flask_sqlalchemy import SQLAlchemy
from enum import Enum
from sqlalchemy.orm import relationship
from app import db
from .TicketModel import TicketModel


class StockModel(db.Model):
    __tablename__ = 'stocks'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    symbol = db.Column(db.String(10), db.ForeignKey('tickets.symbol', name='fk_stocks_tickets'), nullable=False)  # Asignar nombre a la FK
    cvm_code = db.Column(db.String(10), nullable=True)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    buy_at = db.Column(db.DateTime, server_default=db.func.now())
    sell_at = db.Column(db.DateTime, nullable=True)
    
    ticket = db.relationship('TicketModel', backref='stocks', lazy=True)  # Cambié `symbol` a `ticket` para mayor claridad
    user = db.relationship('UserModel', backref='stocks', lazy=True)
    
    def __repr__(self):
        return f"<StockModel(symbol={self.symbol}, quantity={self.quantity}, price={self.price})>"
    
    def serialize(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'symbol': self.symbol.symbol,
            'quantity': self.quantity,
            'price': self.price,
            'buy_at': self.buy_at,
            'sell_at': self.sell_at
        }
    
    def get_averages_stock_price(user_id, symbol):
        return StockModel.query.filter_by(user_id=user_id, symbol=symbol).with_entities(db.func.avg(StockModel.price)).scalar() or 0.0
    
    def get_adquisition_cost(user_id):
        return StockModel.query.filter_by(user_id=user_id).with_entities(db.func.sum(StockModel.price)).scalar() or 0.0
    
    