from app import db
from enum import Enum

class OrderType(Enum):
    BUY = 'BUY'
    SELL = 'SELL'

class OrderModel(db.Model):
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    stock_id = db.Column(db.Integer, db.ForeignKey('stocks.symbol', name='fk_orders_stocks'), nullable=False)
    type = db.Column(db.Enum(OrderType), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    
    
    stock = db.relationship('StockModel', backref='orders', lazy=True)
    user = db.relationship('UserModel', backref='orders', lazy=True)
    
        
    def __repr__(self):
        return f'<OrderModel(type={self.type}, quantity={self.quantity}, price={self.price}, date={self.date})>'
    
    def serialize(self):
       return {
              "id": self.id,
              "user_id": self.user_id,
              "stock_id": self.stock_id,
              "type": self.type,
              "quantity": self.quantity,
              "price": self.price,
              "date": self.date, 
              "stock": self.stock
         }
       