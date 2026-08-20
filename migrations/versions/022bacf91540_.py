"""accounts + orders redesign for Fase 3 (Portafolio v2)

Revision ID: 022bacf91540
Revises: 1779d5844790
Create Date: 2026-08-20 10:00:00.000000

Adds `accounts` (TFSA/RRSP/FHSA/MARGIN/CASH) and redesigns `orders` for the
Canadian pivot: account_id, fees, currency, fx_rate_to_cad, broker,
import_hash, executed_at (renamed from `date`), quantity as Float (fractional
shares). Drops `portfolios` — it was a materialized cache with a live
duplication bug (rows appended on every re-import, never deduped); positions
are now computed on the fly by `PortfolioService` from `orders`, never
persisted. Per product decision, `instance/finance.db` is reset before this
migration runs, so there is no legacy data to backfill.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '022bacf91540'
down_revision = '1779d5844790'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'accounts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.Enum('TFSA', 'RRSP', 'FHSA', 'MARGIN', 'CASH', name='accounttype'), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('broker', sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'name', name='uq_accounts_user_name'),
    )
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_accounts_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('account_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('fees', sa.Float(), nullable=False, server_default='0.0'))
        batch_op.add_column(sa.Column('currency', sa.String(length=3), nullable=False, server_default='CAD'))
        batch_op.add_column(sa.Column('fx_rate_to_cad', sa.Float(), nullable=False, server_default='1.0'))
        batch_op.add_column(sa.Column('broker', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('import_hash', sa.String(length=64), nullable=True))
        batch_op.alter_column('quantity', existing_type=sa.Integer(), type_=sa.Float(), nullable=False)
        batch_op.alter_column('date', new_column_name='executed_at', existing_type=sa.DateTime())

    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.alter_column('account_id', existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key('fk_orders_account_id', 'accounts', ['account_id'], ['id'])
        batch_op.create_index(batch_op.f('ix_orders_import_hash'), ['import_hash'], unique=True)

    op.drop_table('portfolios')


def downgrade():
    op.create_table(
        'portfolios',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('asset_id', sa.Integer(), nullable=False),
        sa.Column('avg_price', sa.Float(), nullable=True),
        sa.Column('actual_price', sa.Float(), nullable=True),
        sa.Column('adquisition_cost', sa.Float(), nullable=False),
        sa.Column('current_cost', sa.Float(), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('profit', sa.Float(), nullable=True),
        sa.Column('percent_return', sa.Float(), nullable=True),
        sa.Column('dividend_amount', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )

    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_orders_import_hash'))
        batch_op.drop_constraint('fk_orders_account_id', type_='foreignkey')
        batch_op.alter_column('executed_at', new_column_name='date', existing_type=sa.DateTime())
        batch_op.alter_column('quantity', existing_type=sa.Float(), type_=sa.Integer(), nullable=False)
        batch_op.drop_column('import_hash')
        batch_op.drop_column('broker')
        batch_op.drop_column('fx_rate_to_cad')
        batch_op.drop_column('currency')
        batch_op.drop_column('fees')
        batch_op.drop_column('account_id')

    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_accounts_user_id'))
    op.drop_table('accounts')
