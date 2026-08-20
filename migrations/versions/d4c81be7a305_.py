"""fundamentals: statement magnitudes + Suno-style derived indicators

Revision ID: d4c81be7a305
Revises: c7a5e1d93f20
Create Date: 2026-08-20 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4c81be7a305'
down_revision = 'c7a5e1d93f20'
branch_labels = None
depends_on = None

NEW_COLUMNS = (
    'revenue',
    'ebit',
    'ebitda',
    'total_assets',
    'total_liabilities',
    'total_equity',
    'tax_rate',
    'total_debt',
    'net_debt',
    'enterprise_value',
    'book_value_per_share',
    'p_ebit',
    'ev_ebit',
    'price_to_assets',
    'ebitda_margin',
    'net_debt_to_equity',
    'net_debt_to_ebitda',
    'liabilities_to_assets',
    'asset_turnover',
    'revenue_cagr',
    'revenue_cagr_years',
)


def upgrade():
    with op.batch_alter_table('fundamentals', schema=None) as batch_op:
        for name in NEW_COLUMNS:
            batch_op.add_column(sa.Column(name, sa.Float(), nullable=True))


def downgrade():
    with op.batch_alter_table('fundamentals', schema=None) as batch_op:
        for name in reversed(NEW_COLUMNS):
            batch_op.drop_column(name)
