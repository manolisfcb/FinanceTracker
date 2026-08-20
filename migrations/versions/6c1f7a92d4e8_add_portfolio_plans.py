"""add portfolio plans

Revision ID: 6c1f7a92d4e8
Revises: 9d2f4c7a1b60
Create Date: 2026-08-20 16:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '6c1f7a92d4e8'
down_revision = '9d2f4c7a1b60'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'portfolio_plans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('equity_etf_percent', sa.Float(), nullable=False, server_default='40'),
        sa.Column('reit_percent', sa.Float(), nullable=False, server_default='30'),
        sa.Column('crypto_percent', sa.Float(), nullable=False, server_default='20'),
        sa.Column('cash_percent', sa.Float(), nullable=False, server_default='10'),
        sa.Column('cash_balance_cad', sa.Float(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
    )
    with op.batch_alter_table('portfolio_plans', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_portfolio_plans_user_id'), ['user_id'], unique=True)


def downgrade():
    with op.batch_alter_table('portfolio_plans', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_portfolio_plans_user_id'))
    op.drop_table('portfolio_plans')
