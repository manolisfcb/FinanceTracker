"""add Canadian personal investment and crypto account types

Revision ID: 9d2f4c7a1b60
Revises: e5b71c9a4d10
Create Date: 2026-08-20 18:00:00.000000
"""
from alembic import op


revision = '9d2f4c7a1b60'
down_revision = 'e5b71c9a4d10'
branch_labels = None
depends_on = None


NEW_ACCOUNT_TYPES = ('RESP', 'RDSP', 'RRIF', 'LIRA', 'LIF', 'JOINT', 'CRYPTO')


def upgrade():
    # SQLite stores SQLAlchemy enums as VARCHAR in this project, so the model
    # change is sufficient there. PostgreSQL uses the native enum and needs
    # each new value registered explicitly.
    if op.get_bind().dialect.name == 'postgresql':
        for account_type in NEW_ACCOUNT_TYPES:
            op.execute(f"ALTER TYPE accounttype ADD VALUE IF NOT EXISTS '{account_type}'")


def downgrade():
    # PostgreSQL cannot safely remove enum values while rows may reference
    # them. Leaving the values in place is data-safe and the previous app
    # version simply will not offer them in its form.
    pass
