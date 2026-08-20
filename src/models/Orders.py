from enum import Enum

from src.extensions import db


class OrderType(Enum):
    BUY = 'BUY'
    SELL = 'SELL'


class OrderModel(db.Model):
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    type = db.Column(db.Enum(OrderType), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False)
    fees = db.Column(db.Float, nullable=False, default=0.0)
    currency = db.Column(db.String(3), nullable=False)
    fx_rate_to_cad = db.Column(db.Float, nullable=False, default=1.0)
    executed_at = db.Column(db.DateTime, nullable=False)
    broker = db.Column(db.String(50), nullable=True)
    import_hash = db.Column(db.String(64), nullable=True, unique=True, index=True)

    asset = db.relationship('Asset', backref='orders', lazy=True)
    user = db.relationship('UserModel', backref='orders', lazy=True)
    account = db.relationship('Account', backref='orders', lazy=True)

    def __repr__(self):
        return f'<OrderModel(type={self.type}, quantity={self.quantity}, price={self.price}, executed_at={self.executed_at})>'

    def serialize(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "asset_id": self.asset_id,
            "account_id": self.account_id,
            "type": self.type.value,
            "quantity": self.quantity,
            "price": self.price,
            "fees": self.fees,
            "currency": self.currency,
            "fx_rate_to_cad": self.fx_rate_to_cad,
            "executed_at": self.executed_at,
            "broker": self.broker,
            "import_hash": self.import_hash,
        }
