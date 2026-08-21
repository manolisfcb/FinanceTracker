from src.extensions import db


class MarketIndicator(db.Model):
    """Latest value of one figure on the site-wide market strip.

    One row per indicator, overwritten in place by the daily market job: the
    strip only ever shows "now", and a history of index levels is not
    something any screen reads.
    """

    __tablename__ = 'market_indicators'

    key = db.Column(db.String(32), primary_key=True)
    label = db.Column(db.String(32), nullable=False)
    value = db.Column(db.Float, nullable=True)
    change_percent = db.Column(db.Float, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False)

    def __repr__(self):
        return f"<MarketIndicator(key={self.key}, value={self.value})>"

    def serialize(self):
        return {
            "key": self.key,
            "label": self.label,
            "value": self.value,
            "change_percent": self.change_percent,
            "updated_at": self.updated_at,
        }
