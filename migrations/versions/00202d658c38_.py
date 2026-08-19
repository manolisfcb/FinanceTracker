"""drop stocks.cvm_code, add portfolio_snapshots

Revision ID: 00202d658c38
Revises: 608df8f5eda7
Create Date: 2026-08-19 17:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '00202d658c38'
down_revision = '608df8f5eda7'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('portfolio_snapshots',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('patrimony', sa.Float(), nullable=False),
    sa.Column('total_invested', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('stocks', schema=None) as batch_op:
        batch_op.drop_column('cvm_code')


def downgrade():
    with op.batch_alter_table('stocks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cvm_code', sa.INTEGER(), nullable=True))

    op.drop_table('portfolio_snapshots')
