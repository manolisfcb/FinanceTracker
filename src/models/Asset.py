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


class AssetType:
    """What the instrument is, independently from its portfolio category."""

    STOCK = 'STOCK'
    ETF = 'ETF'
    CRYPTO = 'CRYPTO'
    INDEX = 'INDEX'
    FX = 'FX'
    MUTUAL_FUND = 'MUTUAL_FUND'
    CASH = 'CASH'

    VALUES = (STOCK, ETF, CRYPTO, INDEX, FX, MUTUAL_FUND, CASH)


class ListingStatus:
    """Provider/listing state. UNKNOWN is deliberately not DELISTED."""

    ACTIVE = 'ACTIVE'
    DELISTED = 'DELISTED'
    SUSPENDED = 'SUSPENDED'
    UNKNOWN = 'UNKNOWN'

    VALUES = (ACTIVE, DELISTED, SUSPENDED, UNKNOWN)


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


def infer_asset_type(*, exchange='', sector='', industry=''):
    """Best-effort classification for legacy and newly discovered assets."""
    exchange = (exchange or '').lower()
    sector = (sector or '').lower()
    industry = (industry or '').lower()
    if exchange == 'crypto' or sector == 'cryptoassets' or industry == 'cryptocurrency':
        return AssetType.CRYPTO
    if sector == 'etfs' or 'exchange-traded fund' in industry:
        return AssetType.ETF
    if exchange == 'index':
        return AssetType.INDEX
    if exchange == 'fx':
        return AssetType.FX
    if exchange == 'cash' or sector == 'cash' or industry == 'cash':
        return AssetType.CASH
    return AssetType.STOCK


class Asset(db.Model):
    __tablename__ = 'assets'
    __table_args__ = (
        db.UniqueConstraint('symbol', 'exchange', name='uq_assets_symbol_exchange'),
        db.CheckConstraint(
            "category IN ('EQUITY', 'REIT', 'FIXED_INCOME', 'CRYPTO', 'CASH')",
            name='ck_assets_category',
        ),
        db.CheckConstraint(
            "asset_type IN ('STOCK', 'ETF', 'CRYPTO', 'INDEX', 'FX', 'MUTUAL_FUND', 'CASH')",
            name='ck_assets_asset_type',
        ),
        db.CheckConstraint(
            "listing_status IN ('ACTIVE', 'DELISTED', 'SUSPENDED', 'UNKNOWN')",
            name='ck_assets_listing_status',
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
    asset_type = db.Column(db.String(20), nullable=False, default=AssetType.STOCK)
    listing_status = db.Column(db.String(20), nullable=False, default=ListingStatus.ACTIVE)
    fundamentals_enabled = db.Column(db.Boolean, nullable=False, default=True)
    market_data_failures = db.Column(db.Integer, nullable=False, default=0)
    last_market_data_success_at = db.Column(db.DateTime, nullable=True)
    last_market_data_failure_at = db.Column(db.DateTime, nullable=True)
    last_viewed_at = db.Column(db.DateTime, nullable=True, index=True)
    last_fundamentals_refresh_at = db.Column(db.DateTime, nullable=True)
    last_dividend_refresh_at = db.Column(db.DateTime, nullable=True)
    last_filings_refresh_at = db.Column(db.DateTime, nullable=True)
    last_news_refresh_at = db.Column(db.DateTime, nullable=True)

    def __init__(self, **kwargs):
        if not kwargs.get('category'):
            kwargs['category'] = infer_asset_category(
                symbol=kwargs.get('symbol'),
                exchange=kwargs.get('exchange'),
                name=kwargs.get('name'),
                sector=kwargs.get('sector'),
                industry=kwargs.get('industry'),
            )
        if not kwargs.get('asset_type'):
            kwargs['asset_type'] = infer_asset_type(
                exchange=kwargs.get('exchange'),
                sector=kwargs.get('sector'),
                industry=kwargs.get('industry'),
            )
        if not kwargs.get('listing_status'):
            kwargs['listing_status'] = (
                ListingStatus.UNKNOWN if kwargs.get('is_active') is False else ListingStatus.ACTIVE
            )
        if 'fundamentals_enabled' not in kwargs:
            kwargs['fundamentals_enabled'] = kwargs['asset_type'] in {
                AssetType.STOCK, AssetType.ETF,
            }
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
            "asset_type": self.asset_type,
            "listing_status": self.listing_status,
            "fundamentals_enabled": self.fundamentals_enabled,
            "market_data_failures": self.market_data_failures,
            "last_market_data_success_at": self.last_market_data_success_at,
            "last_viewed_at": self.last_viewed_at,
        }
