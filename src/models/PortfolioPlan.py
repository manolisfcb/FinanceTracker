from src.extensions import db


class PortfolioPlan(db.Model):
    """User-defined strategic allocation and manually tracked cash balance."""

    __tablename__ = 'portfolio_plans'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True, index=True
    )
    equity_etf_percent = db.Column(db.Float, nullable=False, default=0.0)
    reit_percent = db.Column(db.Float, nullable=False, default=0.0)
    fixed_income_percent = db.Column(db.Float, nullable=False, default=0.0)
    crypto_percent = db.Column(db.Float, nullable=False, default=0.0)
    cash_percent = db.Column(db.Float, nullable=False, default=0.0)
    # Cash is not represented by an order in the current portfolio model, so
    # the user can include the liquid balance that should participate in the
    # current-vs-target comparison.
    cash_balance_cad = db.Column(db.Float, nullable=False, default=0.0)
    updated_at = db.Column(
        db.DateTime, nullable=False, server_default=db.func.now(), onupdate=db.func.now()
    )

    user = db.relationship('UserModel', backref=db.backref('portfolio_plan', uselist=False))

    def serialize(self):
        return {
            'equity_etf_percent': self.equity_etf_percent,
            'reit_percent': self.reit_percent,
            'fixed_income_percent': self.fixed_income_percent,
            'crypto_percent': self.crypto_percent,
            'cash_percent': self.cash_percent,
            'cash_balance_cad': self.cash_balance_cad,
        }
