from src.extensions import db


class DividendReceived(db.Model):
    __tablename__ = 'dividend_received'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'asset_id', 'pay_date', name='uq_dividend_received_user_asset_paydate'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False, index=True)
    pay_date = db.Column(db.Date, nullable=False)
    quantity_held = db.Column(db.Float, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), nullable=False)
    confirmed = db.Column(db.Boolean, nullable=False, default=False)
    # Suggested rows the user rejected. Without this flag, deleting one would
    # just be recreated by the next sync_suggested_dividends() run.
    dismissed = db.Column(db.Boolean, nullable=False, default=False)

    user = db.relationship('UserModel', backref='dividends_received', lazy=True)
    asset = db.relationship('Asset', backref='dividends_received', lazy=True)

    def __repr__(self):
        return f"<DividendReceived(user_id={self.user_id}, asset_id={self.asset_id}, pay_date={self.pay_date}, confirmed={self.confirmed})>"

    def serialize(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "asset_id": self.asset_id,
            "pay_date": self.pay_date,
            "quantity_held": self.quantity_held,
            "total_amount": self.total_amount,
            "currency": self.currency,
            "confirmed": self.confirmed,
            "dismissed": self.dismissed,
        }
