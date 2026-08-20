import re

from src.extensions import db


class AssetCategory:
    """Stable values persisted in ``assets.category``."""

    EQUITY = 'EQUITY'
    REIT = 'REIT'
    FIXED_INCOME = 'FIXED_INCOME'
    CRYPTO = 'CRYPTO'
    CASH = 'CASH'

    VALUES = (EQUITY, REIT, FIXED_INCOME, CRYPTO, CASH)


ASSET_CATEGORY_LABELS = {
    AssetCategory.EQUITY: 'Acciones',
    AssetCategory.REIT: 'REITs',
    AssetCategory.FIXED_INCOME: 'Renta fija',
    AssetCategory.CRYPTO: 'Cripto',
    AssetCategory.CASH: 'Cash',
}


def infer_asset_category(*, symbol='', exchange='', name='', sector='', industry=''):
    """Classify newly discovered/seeded assets before they reach the DB.

    ETF is intentionally checked before its underlying exposure: every ETF,
    including a bond or real-estate ETF, belongs to equities per the product
    rule. Brazilian FII instruments share the REIT bucket.
    """
    symbol = (symbol or '').lower()
    exchange = (exchange or '').lower()
    name = (name or '').lower()
    sector = (sector or '').lower()
    industry = (industry or '').lower()
    combined = ' '.join((symbol, name, sector, industry))

    if exchange == 'crypto' or sector == 'cryptoassets' or industry == 'cryptocurrency':
        return AssetCategory.CRYPTO
    if sector == 'etfs' or 'exchange-traded fund' in industry:
        return AssetCategory.EQUITY
    if (
        industry.startswith('reit')
        or re.search(r'\breit\b', combined)
        or re.search(r'\bfii\b', combined)
        or 'fundo de investimento imobiliario' in combined
        or 'fundo de investimento imobiliário' in combined
    ):
        return AssetCategory.REIT
    if any(term in combined for term in (
        'fixed income', 'renda fixa', 'bond', 'treasury', 'tesoro', 'tesouro',
        'debenture', 'debênture', 'government debt', 'corporate debt',
    )):
        return AssetCategory.FIXED_INCOME
    if exchange == 'cash' or sector == 'cash' or industry == 'cash':
        return AssetCategory.CASH
    return AssetCategory.EQUITY


class Asset(db.Model):
    __tablename__ = 'assets'
    __table_args__ = (
        db.UniqueConstraint('symbol', 'exchange', name='uq_assets_symbol_exchange'),
        db.CheckConstraint(
            "category IN ('EQUITY', 'REIT', 'FIXED_INCOME', 'CRYPTO', 'CASH')",
            name='ck_assets_category',
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), nullable=False)
    yahoo_symbol = db.Column(db.String(15), nullable=False)
    exchange = db.Column(db.String(10), nullable=False)
    currency = db.Column(db.String(3), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(20), nullable=False)
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

    def __init__(self, **kwargs):
        if not kwargs.get('category'):
            kwargs['category'] = infer_asset_category(
                symbol=kwargs.get('symbol'),
                exchange=kwargs.get('exchange'),
                name=kwargs.get('name'),
                sector=kwargs.get('sector'),
                industry=kwargs.get('industry'),
            )
        super().__init__(**kwargs)

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
            "category": self.category,
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
