"""allocation_targets table

Revision ID: fd25f982cca1
Revises: fe8354a9dfde
Create Date: 2026-08-20 10:15:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fd25f982cca1'
down_revision = 'fe8354a9dfde'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'allocation_targets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('asset_id', sa.Integer(), nullable=False),
        sa.Column('target_percent', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'asset_id', name='uq_allocation_targets_user_asset'),
    )
    with op.batch_alter_table('allocation_targets', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_allocation_targets_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_allocation_targets_asset_id'), ['asset_id'], unique=False)


def downgrade():
    with op.batch_alter_table('allocation_targets', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_allocation_targets_asset_id'))
        batch_op.drop_index(batch_op.f('ix_allocation_targets_user_id'))
    op.drop_table('allocation_targets')
