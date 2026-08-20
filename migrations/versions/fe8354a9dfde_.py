"""dividend_received table

Revision ID: fe8354a9dfde
Revises: b8330b9dcc75
Create Date: 2026-08-20 10:10:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fe8354a9dfde'
down_revision = 'b8330b9dcc75'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'dividend_received',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('asset_id', sa.Integer(), nullable=False),
        sa.Column('pay_date', sa.Date(), nullable=False),
        sa.Column('quantity_held', sa.Float(), nullable=False),
        sa.Column('total_amount', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('confirmed', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'asset_id', 'pay_date', name='uq_dividend_received_user_asset_paydate'),
    )
    with op.batch_alter_table('dividend_received', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_dividend_received_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_dividend_received_asset_id'), ['asset_id'], unique=False)


def downgrade():
    with op.batch_alter_table('dividend_received', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_dividend_received_asset_id'))
        batch_op.drop_index(batch_op.f('ix_dividend_received_user_id'))
    op.drop_table('dividend_received')
