from src.extensions import db


class AllocationTarget(db.Model):
    """A planned weight for one sector of the portfolio.

    Targets are set per sector rather than per asset: the plan is about how
    the money is spread across the economy, and which specific names carry a
    sector is a separate decision that changes far more often than the plan.
    The sector string is the one stored on `Asset.sector`, so a target only
    matches holdings if it is spelled exactly the same — the form offers the
    sectors already present in the portfolio instead of free text.
    """

    __tablename__ = 'allocation_targets'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'sector', name='uq_allocation_targets_user_sector'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    sector = db.Column(db.String(100), nullable=False, index=True)
    target_percent = db.Column(db.Float, nullable=False)

    user = db.relationship('UserModel', backref='allocation_targets', lazy=True)

    def __repr__(self):
        return f"<AllocationTarget(user_id={self.user_id}, sector={self.sector}, target_percent={self.target_percent})>"

    def serialize(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "sector": self.sector,
            "target_percent": self.target_percent,
        }
