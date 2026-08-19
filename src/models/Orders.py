from src.extensions import db
from enum import Enum

class OrderType(Enum):
    BUY = 'BUY'
    SELL = 'SELL'

class OrderModel(db.Model):
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False)
    type = db.Column(db.Enum(OrderType), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, nullable=False)


    asset = db.relationship('Asset', backref='orders', lazy=True)
    user = db.relationship('UserModel', backref='orders', lazy=True)
    
        
    def __repr__(self):
        return f'<OrderModel(type={self.type}, quantity={self.quantity}, price={self.price}, date={self.date})>'
    
    def serialize(self):
       return {
              "id": self.id,
              "user_id": self.user_id,
              "asset_id": self.asset_id,
              "type": self.type,
              "quantity": self.quantity,
              "price": self.price,
              "date": self.date,
              "asset": self.asset
         }
       