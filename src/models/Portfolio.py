from app import db


class PortfolioModel(db.Model):
    __tablename__ = 'portfolios'
    
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    stock_id = db.Column(db.Integer, db.ForeignKey('stocks.id'), nullable=False)
    avg_price = db.Column(db.Float, nullable=True)
    actual_price = db.Column(db.Float, nullable=True)
    adquisition_cost = db.Column(db.Float, nullable=False)
    current_cost = db.Column(db.Float, nullable=True)
    quantity = db.Column(db.Integer, nullable=False)
    profit = db.Column(db.Float, nullable=True)
    percent_return = db.Column(db.Float, nullable=True)
    dividend_amount = db.Column(db.Float, nullable=True)
    
    stock = db.relationship('StockModel', backref='portfolios', lazy=True)
    user = db.relationship('UserModel', backref='portfolios', lazy=True)
    
    
    def __repr__(self):
        return f'<PortfolioModel(user_id={self.user_id}, stock_id={self.stock_id}, avg_price={self.avg_price}, actual_price={self.actual_price}, adquisition_cost={self.adquisition_cost}, quantity={self.quantity}, profit={self.profit}, percent_return={self.percent_return}, dividend_amount={self.dividend_amount})>'
    
    
    def serialize(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "stock_id": self.stock_id,
            "avg_price": self.avg_price,
            "quantity": self.quantity,
            "profit": self.profit,
            "percent_return": self.percent_return,
            "dividend_amount": self.dividend_amount,
            "stock": self.stock.serialize(),
        }
        