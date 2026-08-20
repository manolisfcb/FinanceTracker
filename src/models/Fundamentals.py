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
    average_volume = db.Column(db.Float, nullable=True)
    fifty_two_week_high = db.Column(db.Float, nullable=True)
    fifty_two_week_low = db.Column(db.Float, nullable=True)

    # -- Balance sheet / income statement magnitudes -----------------------
    # Absolute figures, in the asset's reporting currency. Stored (rather
    # than only their ratios) because the page shows deuda bruta/neta as
    # amounts, and because keeping the inputs makes every derived ratio
    # below auditable against the filing it came from.
    revenue = db.Column(db.Float, nullable=True)
    ebit = db.Column(db.Float, nullable=True)
    ebitda = db.Column(db.Float, nullable=True)
    total_assets = db.Column(db.Float, nullable=True)
    total_liabilities = db.Column(db.Float, nullable=True)
    total_equity = db.Column(db.Float, nullable=True)
    # Effective tax rate as reported in the income statement — kept because
    # ROIC is built from EBIT after tax, and re-deriving it from a snapshot
    # that carried the statements forward needs the same rate.
    tax_rate = db.Column(db.Float, nullable=True)
    total_debt = db.Column(db.Float, nullable=True)
    net_debt = db.Column(db.Float, nullable=True)
    enterprise_value = db.Column(db.Float, nullable=True)

    # -- Derived indicators -----------------------------------------------
    book_value_per_share = db.Column(db.Float, nullable=True)   # VPA
    p_ebit = db.Column(db.Float, nullable=True)
    ev_ebit = db.Column(db.Float, nullable=True)
    price_to_assets = db.Column(db.Float, nullable=True)
    ebitda_margin = db.Column(db.Float, nullable=True)
    net_debt_to_equity = db.Column(db.Float, nullable=True)
    net_debt_to_ebitda = db.Column(db.Float, nullable=True)
    liabilities_to_assets = db.Column(db.Float, nullable=True)
    asset_turnover = db.Column(db.Float, nullable=True)
    revenue_cagr = db.Column(db.Float, nullable=True)
    # Fiscal years the CAGR above actually spans. Free Yahoo statements carry
    # four usable years for most companies, so the label is built from this
    # rather than hardcoding "5A".
    revenue_cagr_years = db.Column(db.Float, nullable=True)

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
            "average_volume": self.average_volume,
            "fifty_two_week_high": self.fifty_two_week_high,
            "fifty_two_week_low": self.fifty_two_week_low,
            "revenue": self.revenue,
            "ebit": self.ebit,
            "ebitda": self.ebitda,
            "total_assets": self.total_assets,
            "total_liabilities": self.total_liabilities,
            "total_equity": self.total_equity,
            "tax_rate": self.tax_rate,
            "total_debt": self.total_debt,
            "net_debt": self.net_debt,
            "enterprise_value": self.enterprise_value,
            "book_value_per_share": self.book_value_per_share,
            "p_ebit": self.p_ebit,
            "ev_ebit": self.ev_ebit,
            "price_to_assets": self.price_to_assets,
            "ebitda_margin": self.ebitda_margin,
            "net_debt_to_equity": self.net_debt_to_equity,
            "net_debt_to_ebitda": self.net_debt_to_ebitda,
            "liabilities_to_assets": self.liabilities_to_assets,
            "asset_turnover": self.asset_turnover,
            "revenue_cagr": self.revenue_cagr,
            "revenue_cagr_years": self.revenue_cagr_years,
        }
