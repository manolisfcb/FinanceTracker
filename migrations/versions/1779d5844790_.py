"""assets: add description (longBusinessSummary from yfinance, used by the
company page's "about" section)

Revision ID: 1779d5844790
Revises: a1f42e9c8b3d
Create Date: 2026-08-19 19:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1779d5844790'
down_revision = 'a1f42e9c8b3d'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('assets', schema=None) as batch_op:
        batch_op.add_column(sa.Column('description', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('assets', schema=None) as batch_op:
        batch_op.drop_column('description')
