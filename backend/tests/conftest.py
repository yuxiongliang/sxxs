"""Pytest fixtures for the FastAPI backend.

The suite is fully isolated from local development data:

* PostgreSQL: a dedicated database ``ant_design_pro_admin_test`` is created on
  first run, its schema is rebuilt from the SQLAlchemy metadata, and demo data
  is seeded exactly once per session.
* Redis: database index ``15`` is used and flushed around every test so that
  refresh tokens and permission snapshots never leak between tests.
* Every test runs inside an outer transaction that is rolled back afterwards,
  so tests are order independent even though they share seeded fixtures.
"""

from __future__ import annotations

import getpass
import os
import pathlib
import tempfile

PG_HOST = os.environ.get("PGHOST", "127.0.0.1")
PG_PORT = int(os.environ.get("PGPORT", "5433"))
PG_USER = os.environ.get("PGUSER", getpass.getuser())
TEST_DB_NAME = "ant_design_pro_admin_test"
TEST_REDIS_DB = 15

# Environment must be configured before any `app.*` module is imported, because
# `app.core.config.settings` is instantiated at import time.
os.environ["DATABASE_URL"] = (
    f"postgresql+asyncpg://{PG_USER}@{PG_HOST}:{PG_PORT}/{TEST_DB_NAME}"
)
os.environ["REDIS_URL"] = f"redis://{PG_HOST}:6379/{TEST_REDIS_DB}"
os.environ["JWT_SECRET"] = "test-only-secret-not-for-production"
os.environ["PUBLIC_BASE_URL"] = "http://testserver"
# Keep generated upload blobs out of the repository (and out of biome's scope).
_PYTEST_UPLOAD_DIR = pathlib.Path(tempfile.mkdtemp(prefix="antd-pro-pytest-uploads-"))
os.environ["UPLOAD_DIR"] = str(_PYTEST_UPLOAD_DIR)
os.environ["COOKIE_SECURE"] = "false"
# Rate limiting is exercised explicitly in tests/test_rate_limit.py; leaving it on
# for every test would make the suite flaky and dependent on request volume.
os.environ["RATE_LIMIT_ENABLED"] = "false"

import asyncpg
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import engine, get_db
from app.core.redis import redis_client
from app.main import app
from app.models.base import Base
from app.seed import seed_demo_data

ADMIN_PASSWORD = "ant.design"
DEMO_PASSWORD = "Antd@123456"
DEMO_TENANT_SLUG = "demo"


async def _ensure_test_database() -> None:
    conn = await asyncpg.connect(
        user=PG_USER, host=PG_HOST, port=PG_PORT, database="postgres"
    )
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", TEST_DB_NAME
        )
        if not exists:
            await conn.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
    finally:
        await conn.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def prepared_database():
    """Create the test database, rebuild the schema and seed demo data once."""
    await _ensure_test_database()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    await seed_demo_data()
    await redis_client.flushdb()
    yield
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await redis_client.flushdb()
    await redis_client.aclose()
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _reset_redis(prepared_database):
    """Keep refresh tokens and permission caches from leaking across tests."""
    await redis_client.flushdb()
    yield
    await redis_client.flushdb()


@pytest_asyncio.fixture
async def db_session():
    """Session bound to an outer transaction that is always rolled back."""
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


@pytest_asyncio.fixture
async def client(db_session):
    """HTTP client talking to the ASGI app with the shared test session."""

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://testserver") as http:
            yield http
    finally:
        app.dependency_overrides.clear()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def login(client: AsyncClient, username: str, password: str) -> dict:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


@pytest_asyncio.fixture
async def admin_token(client) -> str:
    return (await login(client, "admin", ADMIN_PASSWORD))["access_token"]


PLATFORM_ADMIN_USERNAME = "root"
PLATFORM_ADMIN_PASSWORD = "Sxxs@Platform2026"


@pytest_asyncio.fixture
async def platform_token(client) -> str:
    """平台端 token（aud=platform）。租户 token 打不了 /api/v1/platform/*。"""
    response = await client.post(
        "/api/v1/platform/auth/login",
        json={"username": PLATFORM_ADMIN_USERNAME, "password": PLATFORM_ADMIN_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["access_token"]


@pytest_asyncio.fixture
async def operator_token(client) -> str:
    """`lisi` holds the operator role: no system settings, no role management."""
    return (await login(client, "lisi", DEMO_PASSWORD))["access_token"]


@pytest_asyncio.fixture
async def viewer_token(client) -> str:
    """`chenqi` holds the read-only viewer role (active account)."""
    return (await login(client, "chenqi", DEMO_PASSWORD))["access_token"]


@pytest_asyncio.fixture
async def customer(client) -> dict:
    """Register a fresh C-end customer and return its auth payload."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "tenant_slug": DEMO_TENANT_SLUG,
            "email": "pytest-customer@example.com",
            "nickname": "测试买家",
            "password": "Buyer@123456",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


@pytest_asyncio.fixture
async def customer_token(customer) -> str:
    return customer["access_token"]
