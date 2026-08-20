from src.extensions import db


class Asset(db.Model):
    __tablename__ = 'assets'
    __table_args__ = (
        db.UniqueConstraint('symbol', 'exchange', name='uq_assets_symbol_exchange'),
    )

    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), nullable=False)
    yahoo_symbol = db.Column(db.String(15), nullable=False)
    exchange = db.Column(db.String(10), nullable=False)
    currency = db.Column(db.String(3), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    sector = db.Column(db.String(100), nullable=True)
    industry = db.Column(db.String(100), nullable=True)
    country = db.Column(db.String(100), nullable=True)
    website = db.Column(db.String(255), nullable=True)
    ir_website = db.Column(db.String(255), nullable=True)
    logo_url = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=True)
    # SEC EDGAR filings are addressed by CIK, not ticker. Filled lazily by the
    # company-events job for held US assets only, not for the whole universe.
    cik = db.Column(db.String(10), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    def __repr__(self):
        return f"<Asset(symbol={self.symbol}, exchange={self.exchange})>"

    def serialize(self):
        return {
            "id": self.id,
            "symbol": self.symbol,
            "yahoo_symbol": self.yahoo_symbol,
            "exchange": self.exchange,
            "currency": self.currency,
            "name": self.name,
            "sector": self.sector,
            "industry": self.industry,
            "country": self.country,
            "website": self.website,
            "ir_website": self.ir_website,
            "logo_url": self.logo_url,
            "description": self.description,
            "cik": self.cik,
            "is_active": self.is_active,
        }
