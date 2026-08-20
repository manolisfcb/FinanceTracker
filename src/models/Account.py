from enum import Enum

from src.extensions import db


class AccountType(Enum):
    TFSA = 'TFSA'
    RRSP = 'RRSP'
    FHSA = 'FHSA'
    RESP = 'RESP'
    RDSP = 'RDSP'
    RRIF = 'RRIF'
    LIRA = 'LIRA'
    LIF = 'LIF'
    MARGIN = 'MARGIN'
    CASH = 'CASH'
    JOINT = 'JOINT'
    CRYPTO = 'CRYPTO'


ACCOUNT_TYPE_LABELS = {
    AccountType.TFSA: 'TFSA — Cuenta de ahorro libre de impuestos',
    AccountType.RRSP: 'RRSP — Ahorro para la jubilación',
    AccountType.FHSA: 'FHSA — Ahorro para la primera vivienda',
    AccountType.RESP: 'RESP — Ahorro para educación',
    AccountType.RDSP: 'RDSP — Ahorro por discapacidad',
    AccountType.RRIF: 'RRIF — Fondo de ingresos de jubilación',
    AccountType.LIRA: 'LIRA — Jubilación bloqueada',
    AccountType.LIF: 'LIF — Fondo de ingresos vitalicios',
    AccountType.MARGIN: 'Margin — Cuenta con margen',
    AccountType.CASH: 'Cash — Cuenta no registrada',
    AccountType.JOINT: 'Joint — Cuenta conjunta',
    AccountType.CRYPTO: 'Crypto — Criptomonedas',
}


REGISTERED_ACCOUNT_TYPES = {
    AccountType.TFSA,
    AccountType.RRSP,
    AccountType.FHSA,
    AccountType.RESP,
    AccountType.RDSP,
    AccountType.RRIF,
    AccountType.LIRA,
    AccountType.LIF,
}


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
