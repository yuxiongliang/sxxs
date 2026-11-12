"""B6：Host → 租户解析。

这几条用例锁死三个不能退让的行为：

1. 未验证的自定义域名绝不能解析出租户（否则等于把「伪装站点」合法化）；
2. 停用租户的域名即使 active 也解析不出来；
3. Host 命中时优先级高于 ?tenant= 参数（否则线上仍能被参数劫持）。
"""

from __future__ import annotations

from typing import Any, cast

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.api.proxy_amap import _tenant_id_for_host
from app.core.config import settings
from app.models.tenant import Tenant, TenantDomain
from app.services import domain_verifier, tenant_domains
from app.services.tenant_domains import (
    DomainConflictError,
    InvalidHostError,
    ReservedHostError,
    normalize_host,
)


@pytest_asyncio.fixture
async def demo_tenant(db_session):
    return (await db_session.scalars(select(Tenant).where(Tenant.slug == "demo"))).first()


async def _make_tenant(db_session, slug: str, name: str, status: str = 'active') -> Tenant:
    tenant = Tenant(name=name, slug=slug, status=status)
    db_session.add(tenant)
    await db_session.flush()
    return tenant


async def _bind(db_session, tenant: Tenant, host: str, status: str = 'active'):
    domain = TenantDomain(tenant_id=tenant.id, host=host, kind='custom', status=status)
    db_session.add(domain)
    await db_session.flush()
    return domain


def _static_verifier() -> domain_verifier.StaticVerifier:
    """测试注入版校验器：记录写在内存里，不依赖真实 DNS。"""
    verifier = domain_verifier.get_verifier()
    assert isinstance(verifier, domain_verifier.StaticVerifier)
    return verifier


class _HostRequest:
    """只带 Host 头的假 Request：_tenant_id_for_host 只读 request.headers。"""

    def __init__(self, host: str) -> None:
        self.headers = {'host': host}


def test_normalize_host_strips_port_path_case_and_trailing_dot():
    assert normalize_host("Demo.Example.COM:8000") == "demo.example.com"
    assert normalize_host("demo.example.com.") == "demo.example.com"
    assert normalize_host("demo.example.com/api/v1") == "demo.example.com"
    assert normalize_host("[::1]:8000") == "::1"
    assert normalize_host("") == ""
    assert normalize_host(None) == ''


def test_normalize_host_punycodes_idn():
    assert normalize_host("例え.jp") == "xn--r8jz45g.jp"


async def test_reserved_and_malformed_hosts_are_rejected(db_session, demo_tenant):
    with pytest.raises(ReservedHostError):
        await tenant_domains.add_domain(db_session, demo_tenant, "localhost")
    with pytest.raises(ReservedHostError):
        await tenant_domains.add_domain(db_session, demo_tenant, "127.0.0.1")
    with pytest.raises(InvalidHostError):
        await tenant_domains.add_domain(db_session, demo_tenant, "no-dot-host")


async def test_same_host_cannot_be_bound_twice(db_session, demo_tenant):
    await tenant_domains.add_domain(db_session, demo_tenant, "shop.example.com")
    with pytest.raises(DomainConflictError):
        await tenant_domains.add_domain(db_session, demo_tenant, "SHOP.example.com")


async def test_unverified_domain_does_not_resolve_then_txt_verifies(
    client, db_session, demo_tenant, monkeypatch
):
    monkeypatch.setattr(settings, "tenant_host_fallback", False)
    monkeypatch.setattr(settings, "domain_verify_provider", "static")
    domain = await tenant_domains.add_domain(db_session, demo_tenant, "shop.example.com")
    assert domain.status == 'pending'
    assert domain.verify_token

    pending = await client.get("/api/v1/public/brand", headers={"host": "shop.example.com"})
    assert pending.status_code == 404, pending.text

    verifier = _static_verifier()
    verifier.set_records(
        tenant_domains.verification_record_name("shop.example.com"),
        [tenant_domains.verification_value(domain.verify_token)],
    )
    await tenant_domains.verify_domain(db_session, domain)
    assert domain.status == 'active'
    assert domain.verified_at is not None

    active = await client.get("/api/v1/public/brand", headers={"host": "shop.example.com"})
    assert active.status_code == 200, active.text
    assert active.json()["data"]["slug"] == "demo"


async def test_wrong_txt_marks_domain_failed(db_session, demo_tenant, monkeypatch):
    monkeypatch.setattr(settings, "domain_verify_provider", "static")
    domain = await tenant_domains.add_domain(db_session, demo_tenant, "wrong.example.com")
    verifier = _static_verifier()
    verifier.set_records(
        tenant_domains.verification_record_name("wrong.example.com"),
        ['sxxs-verify=not-the-token'],
    )
    await tenant_domains.verify_domain(db_session, domain)
    assert domain.status == 'failed'
    verifier.set_records(tenant_domains.verification_record_name('wrong.example.com'), [])


async def test_suspended_tenant_domain_does_not_resolve(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "tenant_host_fallback", False)
    tenant = await _make_tenant(db_session, "suspended-market", "停用站", status="suspended")
    await _bind(db_session, tenant, "closed.example.com")

    response = await client.get("/api/v1/public/brand", headers={"host": "closed.example.com"})
    assert response.status_code == 404, response.text


async def test_host_beats_tenant_query_param_and_isolates_tenants(client, db_session):
    tenant = await _make_tenant(db_session, "other-market", "别家市场")
    await _bind(db_session, tenant, "other.example.com")

    response = await client.get(
        "/api/v1/public/brand?tenant=demo", headers={"host": "other.example.com"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["slug"] == "other-market"


async def test_subdomain_comes_from_base_domain_and_is_active(
    db_session, demo_tenant, monkeypatch
):
    monkeypatch.setattr(settings, "tenant_base_domain", "com.sxxs.cn")
    domain = await tenant_domains.ensure_tenant_subdomain(db_session, demo_tenant)
    assert domain is not None
    assert domain.host == "demo.com.sxxs.cn"
    assert domain.status == 'active'
    assert domain.verify_token is None

    again = await tenant_domains.ensure_tenant_subdomain(db_session, demo_tenant)
    assert again is not None
    assert again.id == domain.id

    with pytest.raises(InvalidHostError):
        await tenant_domains.add_domain(
            db_session, demo_tenant, "evil.com.sxxs.cn", kind="subdomain"
        )


async def test_amap_proxy_resolves_tenant_from_host(db_session, demo_tenant):
    await _bind(db_session, demo_tenant, "shop.example.com")

    bound = cast(Any, _HostRequest('shop.example.com:8000'))
    unknown = cast(Any, _HostRequest('nowhere.example.com'))

    assert await _tenant_id_for_host(db_session, bound) == demo_tenant.id
    assert await _tenant_id_for_host(db_session, unknown) == 1  # DEMO_TENANT_ID 兜底
