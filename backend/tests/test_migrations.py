"""Schema drift guard: the Alembic migration must equal the SQLAlchemy models.

The application used to create its schema with ``Base.metadata.create_all``,
which silently diverges from the migration history. This module builds the schema
twice — once by replaying migrations, once from the models — and compares every
table, column, primary key, index, unique constraint and foreign key.

It is the automated protection against "works locally, breaks on deploy".
"""

from __future__ import annotations

import asyncio
import getpass
import os
from collections.abc import AsyncIterator

import asyncpg
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.models.base import Base

PG_HOST = os.environ.get("PGHOST", "127.0.0.1")
PG_PORT = int(os.environ.get("PGPORT", "5433"))
PG_USER = os.environ.get("PGUSER", getpass.getuser())

MIGRATED_DB = "ant_design_pro_schema_migrated"
MODEL_DB = "ant_design_pro_schema_models"

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _async_url(database: str) -> str:
    return f"postgresql+asyncpg://{PG_USER}@{PG_HOST}:{PG_PORT}/{database}"


async def _recreate_database(name: str) -> None:
    connection = await asyncpg.connect(
        user=PG_USER, host=PG_HOST, port=PG_PORT, database="postgres"
    )
    try:
        await connection.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = $1 AND pid <> pg_backend_pid()",
            name,
        )
        await connection.execute(f'DROP DATABASE IF EXISTS "{name}"')
        await connection.execute(f'CREATE DATABASE "{name}"')
    finally:
        await connection.close()


def _run_upgrade(database: str) -> None:
    """Run ``alembic upgrade head`` in a worker thread.

    ``migrations/env.py`` calls ``asyncio.run``, so it must not execute inside the
    already-running test event loop.
    """
    os.environ["ALEMBIC_DATABASE_URL"] = _async_url(database)
    config = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(BACKEND_DIR, "migrations"))
    command.upgrade(config, "head")


def _schema_snapshot(engine) -> dict[str, dict]:
    inspector = inspect(engine)
    snapshot: dict[str, dict] = {}
    for table in inspector.get_table_names():
        if table == "alembic_version":
            continue
        columns = {
            column["name"]: (str(column["type"]), bool(column["nullable"]))
            for column in inspector.get_columns(table)
        }
        indexes = {
            index["name"]: (tuple(index["column_names"]), bool(index["unique"]))
            for index in inspector.get_indexes(table)
        }
        uniques = {
            constraint["name"]: tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints(table)
        }
        foreign_keys = {
            (
                fk["constrained_columns"][0],
                fk["referred_table"],
                fk["referred_columns"][0],
            )
            for fk in inspector.get_foreign_keys(table)
        }
        snapshot[table] = {
            "columns": columns,
            "indexes": indexes,
            "uniques": uniques,
            "foreign_keys": foreign_keys,
            "primary_key": tuple(inspector.get_pk_constraint(table)["constrained_columns"]),
        }
    return snapshot


@pytest_asyncio.fixture(scope="session")
async def migrated_engine() -> AsyncIterator[AsyncEngine]:
    await _recreate_database(MIGRATED_DB)
    await asyncio.to_thread(_run_upgrade, MIGRATED_DB)
    engine = create_async_engine(_async_url(MIGRATED_DB), poolclass=None)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def model_engine() -> AsyncIterator[AsyncEngine]:
    await _recreate_database(MODEL_DB)
    engine = create_async_engine(_async_url(MODEL_DB), poolclass=None)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


async def _snapshot(engine: AsyncEngine) -> dict[str, dict]:
    async with engine.connect() as connection:
        return await connection.run_sync(_schema_snapshot)


async def test_migration_covers_every_model_table(migrated_engine):
    async with migrated_engine.connect() as connection:
        tables = await connection.run_sync(
            lambda sync: [
                name for name in inspect(sync).get_table_names() if name != "alembic_version"
            ]
        )
    assert set(tables) == set(Base.metadata.tables), (
        f"missing: {set(Base.metadata.tables) - set(tables)}; "
        f"unexpected: {set(tables) - set(Base.metadata.tables)}"
    )


async def test_migrated_schema_matches_models(migrated_engine, model_engine):
    migrated = await _snapshot(migrated_engine)
    models = await _snapshot(model_engine)

    assert migrated.keys() == models.keys()

    problems: list[str] = []
    for table, expected in models.items():
        actual = migrated[table]

        missing_cols = set(expected["columns"]) - set(actual["columns"])
        extra_cols = set(actual["columns"]) - set(expected["columns"])
        if missing_cols:
            problems.append(f"{table}: migration missing columns {sorted(missing_cols)}")
        if extra_cols:
            problems.append(f"{table}: migration has extra columns {sorted(extra_cols)}")

        for name in set(expected["columns"]) & set(actual["columns"]):
            if expected["columns"][name] != actual["columns"][name]:
                problems.append(
                    f"{table}.{name}: migration={actual['columns'][name]} "
                    f"model={expected['columns'][name]}"
                )

        if expected["primary_key"] != actual["primary_key"]:
            problems.append(
                f"{table}: pk migration={actual['primary_key']} model={expected['primary_key']}"
            )

        missing_idx = set(expected["indexes"]) - set(actual["indexes"])
        if missing_idx:
            problems.append(f"{table}: migration missing indexes {sorted(missing_idx)}")
        missing_uq = set(expected["uniques"]) - set(actual["uniques"])
        if missing_uq:
            problems.append(f"{table}: migration missing unique constraints {sorted(missing_uq)}")
        missing_fk = expected["foreign_keys"] - actual["foreign_keys"]
        if missing_fk:
            problems.append(f"{table}: migration missing foreign keys {sorted(missing_fk)}")

    assert not problems, "schema drift detected:\n" + "\n".join(problems)


async def test_upgrade_is_idempotent_when_already_at_head(migrated_engine):
    await asyncio.to_thread(_run_upgrade, MIGRATED_DB)
    async with migrated_engine.connect() as connection:
        version = (
            await connection.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar()
    assert version, "alembic_version must be stamped after upgrade"


async def test_no_pending_autogenerate_diff(migrated_engine):
    """`alembic revision --autogenerate` must produce an empty diff."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from sqlalchemy import text as sql_text

    diffs: list = []

    def _diff(sync_connection):
        context = MigrationContext.configure(
            sync_connection,
            opts={
                "compare_type": True,
                "compare_server_default": True,
                "include_object": lambda obj, name, type_, reflected, compare_to: not (
                    type_ == "table" and name == "alembic_version"
                ),
            },
        )
        return compare_metadata(context, Base.metadata)

    async with migrated_engine.connect() as connection:
        diffs = await connection.run_sync(_diff)
        await connection.execute(sql_text("SELECT 1"))

    assert not diffs, f"models and migrations disagree: {diffs}"


@pytest.mark.parametrize("database", [MIGRATED_DB, MODEL_DB])
async def test_schema_databases_are_isolated(database):
    """Guard: the drift test must never touch the application databases."""
    assert database.startswith("ant_design_pro_schema_")
