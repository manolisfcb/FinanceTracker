"""persist asset categories and add fixed income portfolio target

Revision ID: c5f0a27d91b4
Revises: b1e1a810de86
Create Date: 2026-08-20 18:30:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'c5f0a27d91b4'
down_revision = 'b1e1a810de86'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('assets', schema=None) as batch_op:
        batch_op.add_column(sa.Column('category', sa.String(length=20), nullable=True))

    # ETF wins over the exposure it tracks: a bond ETF is still categorized
    # as EQUITY. FII is the Brazilian real-estate-fund equivalent of a REIT.
    op.execute(sa.text("""
        UPDATE assets
        SET category = CASE
            WHEN lower(coalesce(exchange, '')) = 'crypto'
              OR lower(coalesce(sector, '')) = 'cryptoassets'
              OR lower(coalesce(industry, '')) = 'cryptocurrency'
                THEN 'CRYPTO'
            WHEN lower(coalesce(sector, '')) = 'etfs'
              OR lower(coalesce(industry, '')) LIKE '%exchange-traded fund%'
                THEN 'EQUITY'
            WHEN lower(coalesce(industry, '')) LIKE 'reit%'
              OR lower(coalesce(name, '')) LIKE '%reit%'
              OR (' ' || lower(coalesce(name, '')) || ' ') LIKE '% fii %'
              OR lower(coalesce(name, '')) LIKE '%fundo de investimento imobili%'
                THEN 'REIT'
            WHEN lower(
                coalesce(name, '') || ' ' || coalesce(sector, '') || ' ' || coalesce(industry, '')
            ) LIKE '%fixed income%'
              OR lower(
                coalesce(name, '') || ' ' || coalesce(sector, '') || ' ' || coalesce(industry, '')
              ) LIKE '%renda fixa%'
              OR lower(
                coalesce(name, '') || ' ' || coalesce(sector, '') || ' ' || coalesce(industry, '')
              ) LIKE '%bond%'
              OR lower(
                coalesce(name, '') || ' ' || coalesce(sector, '') || ' ' || coalesce(industry, '')
              ) LIKE '%treasury%'
              OR lower(
                coalesce(name, '') || ' ' || coalesce(sector, '') || ' ' || coalesce(industry, '')
              ) LIKE '%tesoro%'
              OR lower(
                coalesce(name, '') || ' ' || coalesce(sector, '') || ' ' || coalesce(industry, '')
              ) LIKE '%tesouro%'
              OR lower(
                coalesce(name, '') || ' ' || coalesce(sector, '') || ' ' || coalesce(industry, '')
              ) LIKE '%debenture%'
              OR lower(
                coalesce(name, '') || ' ' || coalesce(sector, '') || ' ' || coalesce(industry, '')
              ) LIKE '%debênture%'
                THEN 'FIXED_INCOME'
            WHEN lower(coalesce(exchange, '')) = 'cash'
              OR lower(coalesce(sector, '')) = 'cash'
              OR lower(coalesce(industry, '')) = 'cash'
                THEN 'CASH'
            ELSE 'EQUITY'
        END
    """))

    with op.batch_alter_table('assets', schema=None) as batch_op:
        batch_op.alter_column(
            'category', existing_type=sa.String(length=20), nullable=False
        )
        batch_op.create_check_constraint(
            'ck_assets_category',
            "category IN ('EQUITY', 'REIT', 'FIXED_INCOME', 'CRYPTO', 'CASH')",
        )

    with op.batch_alter_table('portfolio_plans', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'fixed_income_percent', sa.Float(), nullable=False, server_default='0'
        ))
        batch_op.alter_column(
            'equity_etf_percent', existing_type=sa.Float(), nullable=False, server_default='0'
        )
        batch_op.alter_column(
            'reit_percent', existing_type=sa.Float(), nullable=False, server_default='0'
        )
        batch_op.alter_column(
            'crypto_percent', existing_type=sa.Float(), nullable=False, server_default='0'
        )
        batch_op.alter_column(
            'cash_percent', existing_type=sa.Float(), nullable=False, server_default='0'
        )


def downgrade():
    with op.batch_alter_table('portfolio_plans', schema=None) as batch_op:
        batch_op.alter_column(
            'cash_percent', existing_type=sa.Float(), nullable=False, server_default='10'
        )
        batch_op.alter_column(
            'crypto_percent', existing_type=sa.Float(), nullable=False, server_default='20'
        )
        batch_op.alter_column(
            'reit_percent', existing_type=sa.Float(), nullable=False, server_default='30'
        )
        batch_op.alter_column(
            'equity_etf_percent', existing_type=sa.Float(), nullable=False, server_default='40'
        )
        batch_op.drop_column('fixed_income_percent')

    with op.batch_alter_table('assets', schema=None) as batch_op:
        batch_op.drop_constraint('ck_assets_category', type_='check')
        batch_op.drop_column('category')
