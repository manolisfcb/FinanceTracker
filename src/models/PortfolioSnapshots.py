from app import db


class PortfolioSnapshotModel(db.Model):
    __tablename__ = 'portfolio_snapshots'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeingKey('users.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    patrimony = db.Column(db.Float, nullable=False)
    total_invested = db.Column(db.Float, nullable=False)
    
    
    user = db.relationship('UserModel', backref='portfolio_snapshots', lazy=True)