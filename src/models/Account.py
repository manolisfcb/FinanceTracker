from enum import Enum

from src.extensions import db


class AccountType(Enum):
    TFSA = 'TFSA'
    RRSP = 'RRSP'
    FHSA = 'FHSA'
    MARGIN = 'MARGIN'
    CASH = 'CASH'


REGISTERED_ACCOUNT_TYPES = {AccountType.TFSA, AccountType.RRSP, AccountType.FHSA}


class Account(db.Model):
    __tablename__ = 'accounts'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'name', name='uq_accounts_user_name'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    type = db.Column(db.Enum(AccountType), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    broker = db.Column(db.String(50), nullable=True)

    user = db.relationship('UserModel', backref='accounts', lazy=True)

    @property
    def is_registered(self):
        return self.type in REGISTERED_ACCOUNT_TYPES

    def __repr__(self):
        return f"<Account(user_id={self.user_id}, type={self.type}, name={self.name})>"

    def serialize(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "type": self.type.value,
            "name": self.name,
            "broker": self.broker,
            "is_registered": self.is_registered,
        }
