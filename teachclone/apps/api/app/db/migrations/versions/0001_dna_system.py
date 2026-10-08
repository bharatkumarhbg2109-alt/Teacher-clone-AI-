"""Add Teacher DNA: teacher_profiles.system_prompt + dna_reports table.

Revision ID: 0001_dna_system
Revises:
Create Date: 2026-08-06

Idempotent: this project normally bootstraps its schema with
``Base.metadata.create_all`` on startup, so this migration checks the live
schema first and only creates what's missing. Safe to run on a DB that was
already create_all-initialised.
"""
from alembic import op
import sqlalchemy as sa

from app.db.types import GUID

revision = "0001_dna_system"
down_revision = None
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    insp = _inspector()
    tables = insp.get_table_names()

    # 1. teacher_profiles.system_prompt (additive column)
    if "teacher_profiles" in tables:
        cols = [c["name"] for c in insp.get_columns("teacher_profiles")]
        if "system_prompt" not in cols:
            op.add_column("teacher_profiles", sa.Column("system_prompt", sa.Text(), nullable=True))

    # 2. dna_reports table
    if "dna_reports" not in tables:
        op.create_table(
            "dna_reports",
            sa.Column("id", GUID(), primary_key=True),
            sa.Column("teacher_profile_id", GUID(),
                      sa.ForeignKey("teacher_profiles.id"), index=True, nullable=False),
            sa.Column("teacher_name", sa.String(), nullable=False, server_default=""),
            sa.Column("analyzed_videos", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_words", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("language", sa.String(), nullable=True),
            sa.Column("model_used", sa.String(), nullable=True),
            sa.Column("report", sa.JSON(), nullable=False),
            sa.Column("system_prompt", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
        )


def downgrade() -> None:
    insp = _inspector()
    if "dna_reports" in insp.get_table_names():
        op.drop_table("dna_reports")
    if "teacher_profiles" in insp.get_table_names():
        cols = [c["name"] for c in insp.get_columns("teacher_profiles")]
        if "system_prompt" in cols:
            op.drop_column("teacher_profiles", "system_prompt")
