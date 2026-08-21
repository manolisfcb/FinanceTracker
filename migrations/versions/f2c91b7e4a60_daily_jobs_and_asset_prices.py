"""daily jobs, typed asset lifecycle and global daily prices

Revision ID: f2c91b7e4a60
Revises: e8a4c2d91f73
Create Date: 2026-08-21 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'f2c91b7e4a60'
down_revision = 'e8a4c2d91f73'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('assets', schema=None) as batch_op:
        batch_op.add_column(sa.Column('asset_type', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('listing_status', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('fundamentals_enabled', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('market_data_failures', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('last_market_data_success_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('last_market_data_failure_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('last_viewed_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('last_fundamentals_refresh_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('last_dividend_refresh_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('last_filings_refresh_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('last_news_refresh_at', sa.DateTime(), nullable=True))

    op.execute("""
        UPDATE assets
        SET asset_type = CASE
            WHEN exchange = 'CRYPTO' OR category = 'CRYPTO' THEN 'CRYPTO'
            WHEN exchange = 'INDEX' THEN 'INDEX'
            WHEN exchange = 'FX' THEN 'FX'
            WHEN exchange = 'CASH' OR category = 'CASH' THEN 'CASH'
            WHEN sector = 'ETFs' OR LOWER(COALESCE(industry, '')) LIKE '%exchange-traded fund%' THEN 'ETF'
            ELSE 'STOCK'
        END,
        listing_status = CASE WHEN is_active THEN 'ACTIVE' ELSE 'UNKNOWN' END,
        market_data_failures = 0
    """)
    op.execute("""
        UPDATE assets
        SET fundamentals_enabled = CASE
            WHEN asset_type IN ('STOCK', 'ETF') AND listing_status = 'ACTIVE' THEN TRUE
            ELSE FALSE
        END
    """)

    with op.batch_alter_table('assets', schema=None) as batch_op:
        batch_op.alter_column('asset_type', existing_type=sa.String(length=20), nullable=False)
        batch_op.alter_column('listing_status', existing_type=sa.String(length=20), nullable=False)
        batch_op.alter_column('fundamentals_enabled', existing_type=sa.Boolean(), nullable=False)
        batch_op.alter_column('market_data_failures', existing_type=sa.Integer(), nullable=False)
        batch_op.create_check_constraint(
            'ck_assets_asset_type',
            "asset_type IN ('STOCK', 'ETF', 'CRYPTO', 'INDEX', 'FX', 'MUTUAL_FUND', 'CASH')",
        )
        batch_op.create_check_constraint(
            'ck_assets_listing_status',
            "listing_status IN ('ACTIVE', 'DELISTED', 'SUSPENDED', 'UNKNOWN')",
        )
        batch_op.create_index('ix_assets_last_viewed_at', ['last_viewed_at'], unique=False)

    with op.batch_alter_table('portfolio_snapshots', schema=None) as batch_op:
        batch_op.add_column(sa.Column('unrealized_pnl_cad', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('realized_pnl_cad', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('total_return_percent', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('allocation', sa.JSON(), nullable=True))

    op.create_table(
        'asset_prices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('asset_id', sa.Integer(), nullable=False),
        sa.Column('price_date', sa.Date(), nullable=False),
        sa.Column('open', sa.Float(), nullable=True),
        sa.Column('close', sa.Float(), nullable=False),
        sa.Column('previous_close', sa.Float(), nullable=True),
        sa.Column('high', sa.Float(), nullable=True),
        sa.Column('low', sa.Float(), nullable=True),
        sa.Column('volume', sa.Float(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('asset_id', 'price_date', name='uq_asset_prices_asset_date'),
    )
    op.create_index('ix_asset_prices_asset_id', 'asset_prices', ['asset_id'], unique=False)
    op.create_index('ix_asset_prices_price_date', 'asset_prices', ['price_date'], unique=False)
    op.create_index('ix_asset_prices_updated_at', 'asset_prices', ['updated_at'], unique=False)
    op.execute("""
        DELETE FROM portfolio_snapshots
        WHERE account_id IS NULL
          AND id NOT IN (
              SELECT MAX(id)
              FROM portfolio_snapshots
              WHERE account_id IS NULL
              GROUP BY user_id, date
          )
    """)
    op.create_index(
        'uq_portfolio_snapshots_user_date_total',
        'portfolio_snapshots', ['user_id', 'date'], unique=True,
        postgresql_where=sa.text('account_id IS NULL'),
        sqlite_where=sa.text('account_id IS NULL'),
    )

    # Preserve the price history already embedded in Fundamentals.
    op.execute("""
        INSERT INTO asset_prices (asset_id, price_date, close, updated_at)
        SELECT asset_id, as_of_date, price, CURRENT_TIMESTAMP
        FROM fundamentals
        WHERE price IS NOT NULL
    """)


def downgrade():
    op.drop_index('uq_portfolio_snapshots_user_date_total', table_name='portfolio_snapshots')
    op.drop_index('ix_asset_prices_updated_at', table_name='asset_prices')
    op.drop_index('ix_asset_prices_price_date', table_name='asset_prices')
    op.drop_index('ix_asset_prices_asset_id', table_name='asset_prices')
    op.drop_table('asset_prices')

    with op.batch_alter_table('portfolio_snapshots', schema=None) as batch_op:
        batch_op.drop_column('allocation')
        batch_op.drop_column('total_return_percent')
        batch_op.drop_column('realized_pnl_cad')
        batch_op.drop_column('unrealized_pnl_cad')

    with op.batch_alter_table('assets', schema=None) as batch_op:
        batch_op.drop_index('ix_assets_last_viewed_at')
        batch_op.drop_constraint('ck_assets_listing_status', type_='check')
        batch_op.drop_constraint('ck_assets_asset_type', type_='check')
        batch_op.drop_column('last_news_refresh_at')
        batch_op.drop_column('last_filings_refresh_at')
        batch_op.drop_column('last_dividend_refresh_at')
        batch_op.drop_column('last_fundamentals_refresh_at')
        batch_op.drop_column('last_viewed_at')
        batch_op.drop_column('last_market_data_failure_at')
        batch_op.drop_column('last_market_data_success_at')
        batch_op.drop_column('market_data_failures')
        batch_op.drop_column('fundamentals_enabled')
        batch_op.drop_column('listing_status')
        batch_op.drop_column('asset_type')
