from src.extensions import db


class PortfolioSnapshotModel(db.Model):
    __tablename__ = 'portfolio_snapshots'
    __table_args__ = (
        # SQLite treats each NULL as distinct, so this constraint alone does
        # NOT prevent two aggregate (account_id IS NULL) rows for the same
        # (user_id, date) -- uniqueness for that case is enforced by the
        # snapshot job's get-or-create-by-filter upsert.
        db.UniqueConstraint('user_id', 'date', 'account_id', name='uq_portfolio_snapshots_user_date_account'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True)
    date = db.Column(db.Date, nullable=False)
    patrimony_cad = db.Column(db.Float, nullable=False)
    total_invested_cad = db.Column(db.Float, nullable=False)
    dividends_accum_cad = db.Column(db.Float, nullable=False)

    user = db.relationship('UserModel', backref='portfolio_snapshots', lazy=True)
    account = db.relationship('Account', backref='portfolio_snapshots', lazy=True)

    def __repr__(self):
        return f'<PortfolioSnapshotModel(user_id={self.user_id}, date={self.date}, account_id={self.account_id})>'

    def serialize(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "account_id": self.account_id,
            "date": self.date,
            "patrimony_cad": self.patrimony_cad,
            "total_invested_cad": self.total_invested_cad,
            "dividends_accum_cad": self.dividends_accum_cad,
        }
