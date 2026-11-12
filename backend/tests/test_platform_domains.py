"""B6：平台端域名管理接口（绑定 / 验证 / 解绑）。

断言重点不是 CRUD 本身，而是三条不能破的约束：

1. 只有平台角色能改域名 —— 租户 token 打平台接口一律 401；
2. 跨租户的 domain_id 一律 404，不能靠猜 id 改别家的域名；
3. 没有校验器时 verify 必须报 503 且域名仍是 pending，绝不能顺手判成 failed。
"""

from __future__ import annotations

from sqlalchemy import select

from app.core.config import settings
from app.models.tenant import Tenant, TenantDomain
from app.services import domain_verifier
from tests.conftest import bearer


async def _demo_tenant_id(client, platform_token) -> int:
    rows = (await client.get("/api/v1/platform/tenants", headers=bearer(platform_token))).json()[
        "data"
    ]
    return next(item["id"] for item in rows if item["slug"] == "demo")


async def _create_domain(client, platform_token, tenant_id, host, kind="custom"):
    return await client.post(
        f"/api/v1/platform/tenants/{tenant_id}/domains",
        headers=bearer(platform_token),
        json={"host": host, "kind": kind},
    )


async def test_create_custom_domain_returns_txt_record(client, platform_token):
    tenant_id = await _demo_tenant_id(client, platform_token)
    created = await _create_domain(client, platform_token, tenant_id, "Shop.Example.com")
    assert created.status_code == 200, created.text
    data = created.json()["data"]
    assert data["host"] == "shop.example.com", "host 必须被规整成小写"
    assert data["status"] == "pending"
    assert data["dns_record"]["name"] == "_sxxs-verify.shop.example.com"
    assert data["dns_record"]["value"].startswith("sxxs-verify=")

    listed = await client.get(
        f"/api/v1/platform/tenants/{tenant_id}/domains", headers=bearer(platform_token)
    )
    assert [row["host"] for row in listed.json()["data"]] == ["shop.example.com"]


async def test_tenant_token_cannot_touch_domains(client, admin_token, platform_token):
    tenant_id = await _demo_tenant_id(client, platform_token)
    response = await client.get(
        f"/api/v1/platform/tenants/{tenant_id}/domains", headers=bearer(admin_token)
    )
    assert response.status_code == 401, response.text


async def test_verify_without_provider_is_503_and_stays_pending(client, platform_token):
    tenant_id = await _demo_tenant_id(client, platform_token)
    domain = (
        await _create_domain(client, platform_token, tenant_id, "pending.example.com")
    ).json()["data"]

    verified = await client.post(
        f"/api/v1/platform/tenants/{tenant_id}/domains/{domain['id']}/verify",
        headers=bearer(platform_token),
    )
    assert verified.status_code == 503, verified.text

    listed = (
        await client.get(
            f"/api/v1/platform/tenants/{tenant_id}/domains", headers=bearer(platform_token)
        )
    ).json()["data"]
    assert listed[0]["status"] == "pending", "没校验器时不能把域名判成 failed"


async def test_verify_promotes_domain_and_host_then_resolves(client, platform_token, monkeypatch):
    monkeypatch.setattr(settings, "domain_verify_provider", "static")
    tenant_id = await _demo_tenant_id(client, platform_token)
    created = (await _create_domain(client, platform_token, tenant_id, "live.example.com")).json()[
        "data"
    ]

    verifier = domain_verifier.get_verifier()
    assert isinstance(verifier, domain_verifier.StaticVerifier)
    verifier.set_records(created["dns_record"]["name"], [created["dns_record"]["value"]])

    verified = await client.post(
        f"/api/v1/platform/tenants/{tenant_id}/domains/{created['id']}/verify",
        headers=bearer(platform_token),
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["data"]["status"] == "active"

    brand = await client.get("/api/v1/public/brand", headers={"host": "live.example.com"})
    assert brand.status_code == 200, brand.text
    assert brand.json()["data"]["slug"] == "demo"
    verifier.set_records(created["dns_record"]["name"], [])


async def test_duplicate_and_reserved_hosts_are_rejected(client, platform_token):
    tenant_id = await _demo_tenant_id(client, platform_token)
    first = await _create_domain(client, platform_token, tenant_id, "dup.example.com")
    assert first.status_code == 200, first.text

    again = await _create_domain(client, platform_token, tenant_id, "DUP.example.com")
    assert again.status_code == 409, again.text

    reserved = await _create_domain(client, platform_token, tenant_id, "localhost")
    assert reserved.status_code == 400, reserved.text

    no_dot = await _create_domain(client, platform_token, tenant_id, "just-a-name")
    assert no_dot.status_code == 400, no_dot.text


async def test_subdomain_needs_base_domain_and_is_active(client, platform_token, monkeypatch):
    tenant_id = await _demo_tenant_id(client, platform_token)
    blocked = await _create_domain(
        client, platform_token, tenant_id, "demo.com.sxxs.cn", "subdomain"
    )
    assert blocked.status_code == 400, blocked.text

    monkeypatch.setattr(settings, "tenant_base_domain", "com.sxxs.cn")
    created = await _create_domain(
        client, platform_token, tenant_id, "demo.com.sxxs.cn", "subdomain"
    )
    assert created.status_code == 200, created.text
    data = created.json()["data"]
    assert data["status"] == "active"
    assert data.get("dns_record") is None, "自有子域不需要 TXT 记录"

    wrong = await _create_domain(client, platform_token, tenant_id, "evil.com.sxxs.cn", "subdomain")
    assert wrong.status_code == 400, wrong.text


async def test_cross_tenant_domain_id_is_404(client, platform_token, db_session):
    demo_id = await _demo_tenant_id(client, platform_token)
    domain = (await _create_domain(client, platform_token, demo_id, "owned.example.com")).json()[
        "data"
    ]

    other = Tenant(name="别家市场", slug="other-market", status="active")
    db_session.add(other)
    await db_session.flush()

    response = await client.delete(
        f"/api/v1/platform/tenants/{other.id}/domains/{domain['id']}",
        headers=bearer(platform_token),
    )
    assert response.status_code == 404, response.text

    still_there = await db_session.scalars(
        select(TenantDomain).where(TenantDomain.id == domain["id"])
    )
    assert still_there.first() is not None


def _new_tenant_payload(slug: str) -> dict:
    return {
        "name": f"站点 {slug}",
        "slug": slug,
        "email": f"owner-{slug}@example.com",
        "nickname": "站长",
        "password": "Subdomain@123456",
    }


async def test_new_tenant_gets_active_subdomain_when_base_domain_is_set(
    client, platform_token, monkeypatch
):
    monkeypatch.setattr(settings, "tenant_base_domain", "com.sxxs.cn")
    created = await client.post(
        "/api/v1/platform/tenants",
        headers=bearer(platform_token),
        json=_new_tenant_payload("subdomain-market"),
    )
    assert created.status_code == 200, created.text
    tenant_id = created.json()["data"]["id"]

    domains = (
        await client.get(
            f"/api/v1/platform/tenants/{tenant_id}/domains", headers=bearer(platform_token)
        )
    ).json()["data"]
    assert [item["host"] for item in domains] == ["subdomain-market.com.sxxs.cn"]
    assert domains[0]["status"] == "active"
    assert domains[0]["kind"] == "subdomain"


async def test_new_tenant_has_no_domain_when_base_domain_is_empty(client, platform_token):
    created = await client.post(
        "/api/v1/platform/tenants",
        headers=bearer(platform_token),
        json=_new_tenant_payload("no-base-market"),
    )
    assert created.status_code == 200, created.text
    tenant_id = created.json()["data"]["id"]

    domains = (
        await client.get(
            f"/api/v1/platform/tenants/{tenant_id}/domains", headers=bearer(platform_token)
        )
    ).json()["data"]
    assert domains == [], "基域没配就不该凭空造域名"


async def test_delete_removes_domain(client, platform_token):
    tenant_id = await _demo_tenant_id(client, platform_token)
    domain = (await _create_domain(client, platform_token, tenant_id, "gone.example.com")).json()[
        "data"
    ]

    removed = await client.delete(
        f"/api/v1/platform/tenants/{tenant_id}/domains/{domain['id']}",
        headers=bearer(platform_token),
    )
    assert removed.status_code == 200, removed.text

    listed = (
        await client.get(
            f"/api/v1/platform/tenants/{tenant_id}/domains", headers=bearer(platform_token)
        )
    ).json()["data"]
    assert listed == []
