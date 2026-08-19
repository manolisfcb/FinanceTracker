from src.extensions import db


class DividendHistory(db.Model):
    __tablename__ = 'dividend_history'
    __table_args__ = (
        db.UniqueConstraint('asset_id', 'ex_date', name='uq_dividend_history_asset_exdate'),
    )

    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False, index=True)
    ex_date = db.Column(db.Date, nullable=False)
    pay_date = db.Column(db.Date, nullable=True)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), nullable=False)

    asset = db.relationship('Asset', backref='dividend_history', lazy=True)

    def __repr__(self):
        return f"<DividendHistory(asset_id={self.asset_id}, ex_date={self.ex_date}, amount={self.amount})>"

    def serialize(self):
        return {
            "id": self.id,
            "asset_id": self.asset_id,
            "ex_date": self.ex_date,
            "pay_date": self.pay_date,
            "amount": self.amount,
            "currency": self.currency,
        }
