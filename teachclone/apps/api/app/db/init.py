"""Dev bootstrap: create any missing tables on startup.

`create_all` is idempotent — it only creates tables that don't exist and never
alters existing ones — so it's safe to call on every boot. Production schema
changes go through Alembic (`alembic upgrade head`).

`ensure_schema_upgrades` additively backfills columns that `create_all` cannot
add to a table that already exists (e.g. the DNA ``system_prompt`` column on an
already-created ``teacher_profiles`` table). It is idempotent and dialect-safe
(SQLite + PostgreSQL both support ``ALTER TABLE ... ADD COLUMN``).
"""
import logging

from sqlalchemy import inspect, text

import app.db.base  # noqa: F401  (registers every model on Base.metadata)
from app.db.session import Base, engine

log = logging.getLogger("teachclone")

# (table, column, DDL type) tuples added after their table already shipped.
_ADDITIVE_COLUMNS = [
    ("teacher_profiles", "system_prompt", "TEXT"),
    ("users", "is_admin", "BOOLEAN DEFAULT FALSE"),
]


async def init_models() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await ensure_schema_upgrades()


async def ensure_schema_upgrades() -> None:
    """Add any missing additive columns to already-existing tables."""
    async with engine.begin() as conn:
        for table, column, ddl_type in _ADDITIVE_COLUMNS:
            try:
                cols = await conn.run_sync(
                    lambda sync_conn, t=table: [
                        c["name"] for c in inspect(sync_conn).get_columns(t)
                    ]
                )
            except Exception:
                # Table doesn't exist yet (fresh DB) — create_all already made
                # it with the column, so nothing to backfill.
                continue
            if column not in cols:
                await conn.execute(
                    text(f'ALTER TABLE {table} ADD COLUMN {column} {ddl_type}')
                )
                log.info("Schema upgrade: added %s.%s", table, column)
