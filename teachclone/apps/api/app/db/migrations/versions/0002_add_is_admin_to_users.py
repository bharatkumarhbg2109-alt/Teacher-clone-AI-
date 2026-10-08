"""Add is_admin Boolean column to users table.

Revision ID: 0002_add_is_admin_to_users
Revises: 0001_dna_system
Create Date: 2026-08-22

Idempotent: checks the live schema first and only adds the column if missing.
Safe to run on a DB that was already create_all-initialised.
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_add_is_admin_to_users"
down_revision = "0001_dna_system"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    insp = _inspector()
    tables = insp.get_table_names()

    if "users" in tables:
        cols = [c["name"] for c in insp.get_columns("users")]
        if "is_admin" not in cols:
            op.add_column(
                "users",
                sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            )


def downgrade() -> None:
    insp = _inspector()
    if "users" in insp.get_table_names():
        cols = [c["name"] for c in insp.get_columns("users")]
        if "is_admin" in cols:
            op.drop_column("users", "is_admin")
