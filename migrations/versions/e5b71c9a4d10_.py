"""allocation_targets: plan by sector instead of by asset

The plan answers "how should the money be spread across the economy", which
is a sector question; which names carry a sector is a separate decision that
changes far more often. Existing rows (if any) can't be translated — an
asset-level target says nothing about the weight its whole sector should
have — so they're dropped rather than guessed at.

Revision ID: e5b71c9a4d10
Revises: d4c81be7a305
Create Date: 2026-08-20 14:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5b71c9a4d10'
down_revision = 'd4c81be7a305'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(sa.text('DELETE FROM allocation_targets'))
    with op.batch_alter_table('allocation_targets') as batch_op:
        batch_op.add_column(sa.Column('sector', sa.String(length=100), nullable=False))
        batch_op.drop_index('ix_allocation_targets_asset_id')
        batch_op.drop_constraint('uq_allocation_targets_user_asset', type_='unique')
        batch_op.drop_column('asset_id')
        batch_op.create_index('ix_allocation_targets_sector', ['sector'])
        batch_op.create_unique_constraint('uq_allocation_targets_user_sector', ['user_id', 'sector'])


def downgrade():
    op.execute(sa.text('DELETE FROM allocation_targets'))
    with op.batch_alter_table('allocation_targets') as batch_op:
        batch_op.add_column(sa.Column('asset_id', sa.Integer(), nullable=False))
        batch_op.drop_index('ix_allocation_targets_sector')
        batch_op.drop_constraint('uq_allocation_targets_user_sector', type_='unique')
        batch_op.drop_column('sector')
        batch_op.create_index('ix_allocation_targets_asset_id', ['asset_id'])
        batch_op.create_unique_constraint('uq_allocation_targets_user_asset', ['user_id', 'asset_id'])
        batch_op.create_foreign_key(
            'fk_allocation_targets_asset_id', 'assets', ['asset_id'], ['id']
        )
