"""stocks -> assets (CA/US catalog) + fundamentals, dividend_history, fx_rates, job_runs

Revision ID: a1f42e9c8b3d
Revises: 00202d658c38
Create Date: 2026-08-19 18:10:00.000000

Alembic autogenerate can't run against this DB: it reflects every table in
the connection, including unrelated legacy tables (`Permit` etc.) mixed into
this dev DB from another project, and chokes on `Permit.ward_id` referencing
a `Ward` table that doesn't exist here (NoSuchTableError). Hand-written
instead of fighting the reflection.

The existing 424 `stocks` rows are legacy Brazil-era (.SA) dev/test data with
1098 dependent `orders` and 13 `portfolios` rows. Per product decision, they
are kept (not dropped) and backfilled with placeholder CA/US-schema values
(exchange='BR', currency='BRL', yahoo_symbol=symbol — the .SA suffix already
makes `symbol` a valid Yahoo symbol) rather than deleted, so existing order
history stays intact. They will not resemble real TSX/NYSE/NASDAQ listings.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1f42e9c8b3d'
down_revision = '00202d658c38'
branch_labels = None
depends_on = None


def upgrade():
    op.rename_table('stocks', 'assets')

    # Step 1: add new columns (nullable for now — backfilled below before
    # being locked down to NOT NULL), drop the columns with no equivalent in
    # the new schema. long_name/short_name are kept one more step, needed to
    # backfill `name`.
    with op.batch_alter_table('assets', schema=None) as batch_op:
        batch_op.add_column(sa.Column('yahoo_symbol', sa.String(length=15), nullable=True))
        batch_op.add_column(sa.Column('exchange', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('currency', sa.String(length=3), nullable=True))
        batch_op.add_column(sa.Column('name', sa.String(length=150), nullable=True))
        batch_op.add_column(sa.Column('ir_website', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('logo_url', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('is_active', sa.Boolean(), server_default=sa.text('1'), nullable=False))
        batch_op.drop_column('root_symbol')
        batch_op.drop_column('floatShares')
        batch_op.drop_column('previous_close')
        batch_op.drop_column('dividend_yield')
        batch_op.drop_column('ex_dividend_date')
        batch_op.drop_column('current_price')
        batch_op.drop_column('fiftyTwoWeekHigh')

    op.execute(
        "UPDATE assets SET "
        "yahoo_symbol = symbol, "
        "exchange = 'BR', "
        "currency = 'BRL', "
        "name = COALESCE(long_name, short_name, symbol)"
    )

    # Step 2: now that every row has a value, lock the backfilled columns
    # down to NOT NULL and drop the columns that fed the backfill.
    with op.batch_alter_table('assets', schema=None) as batch_op:
        batch_op.alter_column('yahoo_symbol', existing_type=sa.String(length=15), nullable=False)
        batch_op.alter_column('exchange', existing_type=sa.String(length=10), nullable=False)
        batch_op.alter_column('currency', existing_type=sa.String(length=3), nullable=False)
        batch_op.alter_column('name', existing_type=sa.String(length=150), nullable=False)
        batch_op.drop_column('long_name')
        batch_op.drop_column('short_name')
        batch_op.create_unique_constraint('uq_assets_symbol_exchange', ['symbol', 'exchange'])

    # orders.stock_id / portfolios.stock_id -> asset_id. The FK target
    # updates automatically to `assets` (SQLite rewrites references to a
    # renamed table), batch mode just needs to rename the column.
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.alter_column('stock_id', new_column_name='asset_id', existing_type=sa.Integer())

    with op.batch_alter_table('portfolios', schema=None) as batch_op:
        batch_op.alter_column('stock_id', new_column_name='asset_id', existing_type=sa.Integer())

    op.create_table(
        'fundamentals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('asset_id', sa.Integer(), nullable=False),
        sa.Column('as_of_date', sa.Date(), nullable=False),
        sa.Column('price', sa.Float(), nullable=True),
        sa.Column('market_cap', sa.Float(), nullable=True),
        sa.Column('pe', sa.Float(), nullable=True),
        sa.Column('forward_pe', sa.Float(), nullable=True),
        sa.Column('pb', sa.Float(), nullable=True),
        sa.Column('ps', sa.Float(), nullable=True),
        sa.Column('ev_ebitda', sa.Float(), nullable=True),
        sa.Column('roe', sa.Float(), nullable=True),
        sa.Column('roa', sa.Float(), nullable=True),
        sa.Column('roic', sa.Float(), nullable=True),
        sa.Column('gross_margin', sa.Float(), nullable=True),
        sa.Column('operating_margin', sa.Float(), nullable=True),
        sa.Column('net_margin', sa.Float(), nullable=True),
        sa.Column('debt_to_equity', sa.Float(), nullable=True),
        sa.Column('current_ratio', sa.Float(), nullable=True),
        sa.Column('quick_ratio', sa.Float(), nullable=True),
        sa.Column('dividend_yield', sa.Float(), nullable=True),
        sa.Column('payout_ratio', sa.Float(), nullable=True),
        sa.Column('dividend_rate', sa.Float(), nullable=True),
        sa.Column('eps', sa.Float(), nullable=True),
        sa.Column('eps_growth_5y', sa.Float(), nullable=True),
        sa.Column('revenue_growth_5y', sa.Float(), nullable=True),
        sa.Column('beta', sa.Float(), nullable=True),
        sa.Column('fifty_two_week_high', sa.Float(), nullable=True),
        sa.Column('fifty_two_week_low', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('asset_id', 'as_of_date', name='uq_fundamentals_asset_date'),
    )
    with op.batch_alter_table('fundamentals', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_fundamentals_asset_id'), ['asset_id'], unique=False)

    op.create_table(
        'dividend_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('asset_id', sa.Integer(), nullable=False),
        sa.Column('ex_date', sa.Date(), nullable=False),
        sa.Column('pay_date', sa.Date(), nullable=True),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('asset_id', 'ex_date', name='uq_dividend_history_asset_exdate'),
    )
    with op.batch_alter_table('dividend_history', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_dividend_history_asset_id'), ['asset_id'], unique=False)

    op.create_table(
        'fx_rates',
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('pair', sa.String(length=6), nullable=False),
        sa.Column('rate', sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint('date'),
    )

    op.create_table(
        'job_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job', sa.String(length=50), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('items_processed', sa.Integer(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('job_runs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_job_runs_job'), ['job'], unique=False)


def downgrade():
    with op.batch_alter_table('job_runs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_job_runs_job'))
    op.drop_table('job_runs')

    op.drop_table('fx_rates')

    with op.batch_alter_table('dividend_history', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_dividend_history_asset_id'))
    op.drop_table('dividend_history')

    with op.batch_alter_table('fundamentals', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_fundamentals_asset_id'))
    op.drop_table('fundamentals')

    with op.batch_alter_table('portfolios', schema=None) as batch_op:
        batch_op.alter_column('asset_id', new_column_name='stock_id', existing_type=sa.Integer())

    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.alter_column('asset_id', new_column_name='stock_id', existing_type=sa.Integer())

    with op.batch_alter_table('assets', schema=None) as batch_op:
        batch_op.drop_constraint('uq_assets_symbol_exchange', type_='unique')
        batch_op.add_column(sa.Column('long_name', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('short_name', sa.String(length=10), nullable=True))

    op.execute("UPDATE assets SET long_name = name")

    with op.batch_alter_table('assets', schema=None) as batch_op:
        batch_op.add_column(sa.Column('root_symbol', sa.String(length=6), nullable=True))
        batch_op.add_column(sa.Column('floatShares', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('previous_close', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('dividend_yield', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('ex_dividend_date', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('current_price', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('fiftyTwoWeekHigh', sa.Float(), nullable=True))
        batch_op.drop_column('is_active')
        batch_op.drop_column('logo_url')
        batch_op.drop_column('ir_website')
        batch_op.drop_column('name')
        batch_op.drop_column('currency')
        batch_op.drop_column('exchange')
        batch_op.drop_column('yahoo_symbol')

    op.rename_table('assets', 'stocks')
