from src.extensions import db


class AllocationTarget(db.Model):
    __tablename__ = 'allocation_targets'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'asset_id', name='uq_allocation_targets_user_asset'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False, index=True)
    target_percent = db.Column(db.Float, nullable=False)

    user = db.relationship('UserModel', backref='allocation_targets', lazy=True)
    asset = db.relationship('Asset', backref='allocation_targets', lazy=True)

    def __repr__(self):
        return f"<AllocationTarget(user_id={self.user_id}, asset_id={self.asset_id}, target_percent={self.target_percent})>"

    def serialize(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "asset_id": self.asset_id,
            "target_percent": self.target_percent,
        }
