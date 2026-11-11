"""Schema management: Alembic replaces ``Base.metadata.create_all``.

The application never creates tables behind Alembic's back any more. On startup
``ensure_schema_at_head()`` brings the database to the latest revision, and it
adopts a legacy database (one created by the old ``create_all`` path) by stamping
the baseline revision before upgrading.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import structlog
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.core.config import settings
from app.core.db import engine

logger = structlog.get_logger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


def _alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    return config


def upgrade_to_head() -> None:
    """Blocking: apply every pending migration."""
    command.upgrade(_alembic_config(), "head")


def stamp_head() -> None:
    """Blocking: record the current schema as being at ``head`` without running it."""
    command.stamp(_alembic_config(), "head")


async def current_revision() -> str | None:
    """Read the revision recorded in ``alembic_version`` (None when unstamped)."""
    from alembic.runtime.migration import MigrationContext

    def _read(sync_connection) -> str | None:
        return MigrationContext.configure(sync_connection).get_current_revision()

    async with engine.connect() as connection:
        return await connection.run_sync(_read)


async def _schema_state() -> tuple[bool, bool]:
    """Return (has_alembic_version, has_application_tables)."""

    def _inspect(sync_connection) -> tuple[bool, bool]:
        inspector = inspect(sync_connection)
        return (
            inspector.has_table("alembic_version"),
            inspector.has_table("users"),
        )

    async with engine.connect() as connection:
        return await connection.run_sync(_inspect)


async def ensure_schema_at_head() -> None:
    """Bring the database to the latest revision (idempotent, safe on restart)."""
    if not settings.db_auto_migrate:
        logger.info("db_auto_migrate_disabled")
        return

    has_version_table, has_tables = await _schema_state()

    if not has_version_table and has_tables:
        # Pre-Alembic database: its schema was produced by create_all, and
        # tests/test_migrations.py proves the baseline equals the models.
        logger.warning(
            "adopting_legacy_schema",
            reason="tables exist without alembic_version; stamping baseline revision",
        )
        await asyncio.to_thread(stamp_head)

    await asyncio.to_thread(upgrade_to_head)
    logger.info("schema_at_head", database=settings.database_url.rsplit("/", 1)[-1])
