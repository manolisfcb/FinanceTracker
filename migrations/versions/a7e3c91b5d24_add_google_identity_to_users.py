"""add google identity to users and make password optional

Revision ID: a7e3c91b5d24
Revises: c5f0a27d91b4
Create Date: 2026-08-20 15:10:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'a7e3c91b5d24'
down_revision = 'c5f0a27d91b4'
branch_labels = None
depends_on = None


def upgrade():
    # SQLite cannot ALTER a column's nullability in place, so the whole table
    # is copied — which is also why `password` has to be widened here rather
    # than in a second pass: werkzeug's scrypt hashes are ~162 characters and
    # the original String(80) would truncate on any backend that enforces it.
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('google_id', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('full_name', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('avatar_url', sa.String(length=512), nullable=True))
        batch_op.alter_column(
            'password',
            existing_type=sa.String(length=80),
            type_=sa.String(length=255),
            nullable=True,
        )
        batch_op.create_index(batch_op.f('ix_users_google_id'), ['google_id'], unique=True)


def downgrade():
    # Accounts created through Google have no password, so they cannot be
    # represented once the column goes back to NOT NULL; they are removed
    # rather than given a hash nobody knows.
    op.execute(sa.text("DELETE FROM users WHERE password IS NULL"))

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_google_id'))
        batch_op.alter_column(
            'password',
            existing_type=sa.String(length=255),
            type_=sa.String(length=80),
            nullable=False,
        )
        batch_op.drop_column('avatar_url')
        batch_op.drop_column('full_name')
        batch_op.drop_column('google_id')
