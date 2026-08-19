from src.extensions import db


class FxRate(db.Model):
    __tablename__ = 'fx_rates'

    date = db.Column(db.Date, primary_key=True)
    pair = db.Column(db.String(6), nullable=False)
    rate = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f"<FxRate(date={self.date}, pair={self.pair}, rate={self.rate})>"

    def serialize(self):
        return {
            "date": self.date,
            "pair": self.pair,
            "rate": self.rate,
        }
