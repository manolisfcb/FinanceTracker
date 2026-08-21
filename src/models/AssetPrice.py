from src.extensions import db


class AssetPrice(db.Model):
    """One global end-of-day price row per asset and trading date."""

    __tablename__ = 'asset_prices'
    __table_args__ = (
        db.UniqueConstraint('asset_id', 'price_date', name='uq_asset_prices_asset_date'),
    )

    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False, index=True)
    price_date = db.Column(db.Date, nullable=False, index=True)
    open = db.Column(db.Float, nullable=True)
    close = db.Column(db.Float, nullable=False)
    previous_close = db.Column(db.Float, nullable=True)
    high = db.Column(db.Float, nullable=True)
    low = db.Column(db.Float, nullable=True)
    volume = db.Column(db.Float, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, index=True)

    asset = db.relationship('Asset', backref='prices', lazy=True)

    def __repr__(self):
        return f"<AssetPrice(asset_id={self.asset_id}, price_date={self.price_date}, close={self.close})>"

    def serialize(self):
        return {
            'id': self.id,
            'asset_id': self.asset_id,
            'date': self.price_date,
            'open': self.open,
            'close': self.close,
            'previous_close': self.previous_close,
            'high': self.high,
            'low': self.low,
            'volume': self.volume,
            'updated_at': self.updated_at,
        }
