"""index orders.user_id and orders.asset_id

Revision ID: b3f8a1c94d02
Revises: f2c91b7e4a60
Create Date: 2026-08-21 13:00:00.000000
"""
from alembic import op


revision = 'b3f8a1c94d02'
down_revision = 'f2c91b7e4a60'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.create_index('ix_orders_user_id', ['user_id'], unique=False)
        batch_op.create_index('ix_orders_asset_id', ['asset_id'], unique=False)


def downgrade():
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_index('ix_orders_asset_id')
        batch_op.drop_index('ix_orders_user_id')
