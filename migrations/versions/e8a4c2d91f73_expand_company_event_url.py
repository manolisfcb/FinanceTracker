"""Store complete company-event source URLs.

Revision ID: e8a4c2d91f73
Revises: a7e3c91b5d24
Create Date: 2026-08-21
"""

from alembic import op
import sqlalchemy as sa


revision = "e8a4c2d91f73"
down_revision = "a7e3c91b5d24"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("company_events", schema=None) as batch_op:
        batch_op.alter_column(
            "url",
            existing_type=sa.String(length=512),
            type_=sa.Text(),
            existing_nullable=True,
        )


def downgrade():
    with op.batch_alter_table("company_events", schema=None) as batch_op:
        batch_op.alter_column(
            "url",
            existing_type=sa.Text(),
            type_=sa.String(length=512),
            existing_nullable=True,
        )
