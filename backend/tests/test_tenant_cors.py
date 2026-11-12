"""B6：跨域放行名单（静态开发来源 + 平台主机 + 已生效的租户域名）。

缓存是进程级的，所以每个用例前后都要 invalidate —— 否则前一个用例绑的域名会污染
后一个用例的「未知来源应当被拒」。
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core import cors
from app.core.config import settings
from app.models.tenant import Tenant, TenantDomain

PREFLIGHT = {"access-control-request-method": "GET"}


class _SessionCtx:
    """把测试事务里的 session 伪装成 AsyncSessionLocal() 的上下文管理器。"""

    def __init__(self, session) -> None:
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *_exc) -> bool:
        return False


@pytest.fixture(autouse=True)
def _reset_cache():
    cors.invalidate_host_cache()
    yield
    cors.invalidate_host_cache()


@pytest.fixture
def cors_reads_test_session(monkeypatch, db_session):
    """中间件默认自己开 session；测试里改成读当前事务，才能看到未提交的域名行。"""
    monkeypatch.setattr(cors, "AsyncSessionLocal", lambda: _SessionCtx(db_session))


async def _bind(db_session, host: str, status: str = "active"):
    tenant = (await db_session.scalars(select(Tenant).where(Tenant.slug == "demo"))).first()
    domain = TenantDomain(tenant_id=tenant.id, host=host, kind="custom", status=status)
    db_session.add(domain)
    await db_session.flush()
    return domain


async def test_static_dev_origin_is_still_allowed(client):
    response = await client.options(
        "/api/v1/public/brand", headers={"origin": "http://localhost:8000", **PREFLIGHT}
    )
    assert response.status_code == 200, response.text
    assert response.headers["access-control-allow-origin"] == "http://localhost:8000"


async def test_active_tenant_domain_is_allowed(client, db_session, cors_reads_test_session):
    await _bind(db_session, "shop.example.com")

    response = await client.options(
        "/api/v1/public/brand",
        headers={"origin": "https://shop.example.com", **PREFLIGHT},
    )
    assert response.status_code == 200, response.text
    assert response.headers["access-control-allow-origin"] == "https://shop.example.com"


async def test_pending_domain_is_not_allowed(client, db_session, cors_reads_test_session):
    await _bind(db_session, "pending.example.com", status="pending")

    response = await client.options(
        "/api/v1/public/brand",
        headers={"origin": "https://pending.example.com", **PREFLIGHT},
    )
    assert response.status_code == 400, response.text
    assert "access-control-allow-origin" not in response.headers


async def test_unknown_origin_is_rejected(client):
    response = await client.options(
        "/api/v1/public/brand",
        headers={"origin": "https://evil.example.net", **PREFLIGHT},
    )
    assert response.status_code == 400, response.text
    assert "access-control-allow-origin" not in response.headers


async def test_platform_host_is_allowed_without_db_row(client, monkeypatch):
    monkeypatch.setattr(settings, "platform_host", "console.example.com")

    response = await client.options(
        "/api/v1/tenants",
        headers={"origin": "https://console.example.com", **PREFLIGHT},
    )
    assert response.status_code == 200, response.text
    assert response.headers["access-control-allow-origin"] == "https://console.example.com"
