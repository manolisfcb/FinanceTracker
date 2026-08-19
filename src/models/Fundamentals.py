from src.extensions import db


class Fundamentals(db.Model):
    __tablename__ = 'fundamentals'
    __table_args__ = (
        db.UniqueConstraint('asset_id', 'as_of_date', name='uq_fundamentals_asset_date'),
    )

    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False, index=True)
    as_of_date = db.Column(db.Date, nullable=False)

    price = db.Column(db.Float, nullable=True)
    market_cap = db.Column(db.Float, nullable=True)
    pe = db.Column(db.Float, nullable=True)
    forward_pe = db.Column(db.Float, nullable=True)
    pb = db.Column(db.Float, nullable=True)
    ps = db.Column(db.Float, nullable=True)
    ev_ebitda = db.Column(db.Float, nullable=True)
    roe = db.Column(db.Float, nullable=True)
    roa = db.Column(db.Float, nullable=True)
    roic = db.Column(db.Float, nullable=True)
    gross_margin = db.Column(db.Float, nullable=True)
    operating_margin = db.Column(db.Float, nullable=True)
    net_margin = db.Column(db.Float, nullable=True)
    debt_to_equity = db.Column(db.Float, nullable=True)
    current_ratio = db.Column(db.Float, nullable=True)
    quick_ratio = db.Column(db.Float, nullable=True)
    dividend_yield = db.Column(db.Float, nullable=True)
    payout_ratio = db.Column(db.Float, nullable=True)
    dividend_rate = db.Column(db.Float, nullable=True)
    eps = db.Column(db.Float, nullable=True)
    eps_growth_5y = db.Column(db.Float, nullable=True)
    revenue_growth_5y = db.Column(db.Float, nullable=True)
    beta = db.Column(db.Float, nullable=True)
    fifty_two_week_high = db.Column(db.Float, nullable=True)
    fifty_two_week_low = db.Column(db.Float, nullable=True)

    asset = db.relationship('Asset', backref='fundamentals', lazy=True)

    def __repr__(self):
        return f"<Fundamentals(asset_id={self.asset_id}, as_of_date={self.as_of_date})>"

    def serialize(self):
        return {
            "id": self.id,
            "asset_id": self.asset_id,
            "as_of_date": self.as_of_date,
            "price": self.price,
            "market_cap": self.market_cap,
            "pe": self.pe,
            "forward_pe": self.forward_pe,
            "pb": self.pb,
            "ps": self.ps,
            "ev_ebitda": self.ev_ebitda,
            "roe": self.roe,
            "roa": self.roa,
            "roic": self.roic,
            "gross_margin": self.gross_margin,
            "operating_margin": self.operating_margin,
            "net_margin": self.net_margin,
            "debt_to_equity": self.debt_to_equity,
            "current_ratio": self.current_ratio,
            "quick_ratio": self.quick_ratio,
            "dividend_yield": self.dividend_yield,
            "payout_ratio": self.payout_ratio,
            "dividend_rate": self.dividend_rate,
            "eps": self.eps,
            "eps_growth_5y": self.eps_growth_5y,
            "revenue_growth_5y": self.revenue_growth_5y,
            "beta": self.beta,
            "fifty_two_week_high": self.fifty_two_week_high,
            "fifty_two_week_low": self.fifty_two_week_low,
        }
