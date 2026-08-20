"""portfolio_snapshots: CAD naming + per-account rows

Revision ID: b8330b9dcc75
Revises: 022bacf91540
Create Date: 2026-08-20 10:05:00.000000

Renames patrimony/total_invested to their explicit *_cad forms (matching the
target ERD), adds dividends_accum_cad, and adds a nullable account_id (NULL =
total across all accounts, non-null = one row per account) so the daily
snapshot job can write both a total and a per-account breakdown. The table
was confirmed empty in the dev DB (nothing has ever populated it — no job
existed for it before Fase 3), so no backfill is needed for dividends_accum_cad.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b8330b9dcc75'
down_revision = '022bacf91540'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('portfolio_snapshots', schema=None) as batch_op:
        batch_op.add_column(sa.Column('account_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('dividends_accum_cad', sa.Float(), nullable=False, server_default='0.0'))
        batch_op.alter_column('patrimony', new_column_name='patrimony_cad', existing_type=sa.Float())
        batch_op.alter_column('total_invested', new_column_name='total_invested_cad', existing_type=sa.Float())
        batch_op.create_foreign_key('fk_portfolio_snapshots_account_id', 'accounts', ['account_id'], ['id'])
        batch_op.create_unique_constraint(
            'uq_portfolio_snapshots_user_date_account', ['user_id', 'date', 'account_id']
        )


def downgrade():
    with op.batch_alter_table('portfolio_snapshots', schema=None) as batch_op:
        batch_op.drop_constraint('uq_portfolio_snapshots_user_date_account', type_='unique')
        batch_op.drop_constraint('fk_portfolio_snapshots_account_id', type_='foreignkey')
        batch_op.alter_column('total_invested_cad', new_column_name='total_invested', existing_type=sa.Float())
        batch_op.alter_column('patrimony_cad', new_column_name='patrimony', existing_type=sa.Float())
        batch_op.drop_column('dividends_accum_cad')
        batch_op.drop_column('account_id')
