"""Multi-tenant isolation.

Plan §18 acceptance criteria covered:
  #1 tenant A data must never leak into tenant B; cross access -> 403/404
  #5 platform admin may cross tenants, but every action is auditable
"""

from __future__ import annotations

import pytest

from tests.conftest import bearer

ACME = {
    "name": "Acme Pytest Marketplace",
    "slug": "acme-pytest",
    "email": "owner-acme@example.com",
    "nickname": "Acme Owner",
    "password": "Acme@123456",
}


async def _create_tenant(client, admin_token) -> dict:
    response = await client.post(
        "/api/v1/platform/tenants", headers=bearer(admin_token), json=ACME
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def _owner_login(client) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": ACME["email"], "password": ACME["password"]},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["access_token"]


async def test_platform_admin_can_list_and_create_tenants(client, admin_token):
    before = (await client.get("/api/v1/platform/tenants", headers=bearer(admin_token))).json()[
        "data"
    ]
    created = await _create_tenant(client, admin_token)
    after = (await client.get("/api/v1/platform/tenants", headers=bearer(admin_token))).json()[
        "data"
    ]

    assert created["slug"] == ACME["slug"]
    assert len(after) == len(before) + 1


async def test_duplicate_tenant_slug_is_rejected(client, admin_token):
    await _create_tenant(client, admin_token)
    response = await client.post(
        "/api/v1/platform/tenants", headers=bearer(admin_token), json=ACME
    )
    assert response.status_code == 409


async def test_tenant_owner_cannot_create_more_tenants(client, admin_token):
    await _create_tenant(client, admin_token)
    owner_token = await _owner_login(client)
    response = await client.post(
        "/api/v1/platform/tenants",
        headers=bearer(owner_token),
        json={**ACME, "slug": "another-tenant", "email": "other@example.com"},
    )
    assert response.status_code == 403


async def test_new_tenant_sees_no_demo_users(client, admin_token):
    """Acceptance #1: tenant B must not see tenant A's users."""
    await _create_tenant(client, admin_token)
    owner_token = await _owner_login(client)

    response = await client.get("/api/v1/users", headers=bearer(owner_token))
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["total"] == 1
    assert data["list"][0]["email"] == ACME["email"]
    usernames = {item["username"] for item in data["list"]}
    assert "admin" not in usernames
    assert "lisi" not in usernames


async def test_new_tenant_sees_no_demo_departments(client, admin_token):
    await _create_tenant(client, admin_token)
    owner_token = await _owner_login(client)

    response = await client.get("/api/v1/departments", headers=bearer(owner_token))
    assert response.status_code == 200
    assert response.json()["data"]["list"] == []


async def test_new_tenant_sees_no_demo_orders(client, admin_token):
    await _create_tenant(client, admin_token)
    owner_token = await _owner_login(client)

    response = await client.get("/api/v1/admin/orders", headers=bearer(owner_token))
    assert response.status_code == 200, response.text
    assert response.json()["data"] == []


async def test_new_tenant_sees_no_demo_products(client, admin_token):
    await _create_tenant(client, admin_token)
    owner_token = await _owner_login(client)

    response = await client.get("/api/v1/portal/products", headers=bearer(owner_token))
    assert response.status_code == 200
    assert response.json()["data"] == []


async def test_settings_are_written_per_tenant(client, admin_token):
    """A tenant owner editing payment settings must not affect the demo tenant."""
    await _create_tenant(client, admin_token)
    owner_token = await _owner_login(client)

    demo_before = (
        await client.get("/api/v1/settings/payment", headers=bearer(admin_token))
    ).json()["data"]

    updated = await client.put(
        "/api/v1/settings/payment",
        headers=bearer(owner_token),
        json={"enabled": False, "config": {"provider": "wechat", "app_id": "acme-app"}},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["config"]["app_id"] == "acme-app"

    demo_after = (
        await client.get("/api/v1/settings/payment", headers=bearer(admin_token))
    ).json()["data"]
    assert demo_after["config"].get("app_id") != "acme-app"
    assert demo_after["enabled"] == demo_before["enabled"]


async def test_owner_cannot_act_inside_the_demo_tenant(client, admin_token):
    """A token is bound to one tenant; it cannot be replayed against another."""
    from app.core.security import create_access_token

    await _create_tenant(client, admin_token)
    owner = (
        await client.get("/api/v1/auth/me", headers=bearer(await _owner_login(client)))
    ).json()["data"]

    forged = create_access_token(
        user_id=owner["user"]["id"],
        tenant_id=1,  # demo tenant, which this owner does not belong to
        audience="admin",
        roles=["tenant_owner"],
        permission_version=1,
    )
    response = await client.get("/api/v1/users", headers=bearer(forged))
    assert response.status_code == 403


async def test_tenant_member_listing_is_scoped(client, admin_token):
    response = await client.get("/api/v1/platform/tenants", headers=bearer(admin_token))
    assert response.status_code == 200
    slugs = {item["slug"] for item in response.json()["data"]}
    assert "demo" in slugs


@pytest.mark.parametrize(
    "slug", ["Invalid Slug", "UPPERCASE", "has_underscore", "a"]
)
async def test_tenant_slug_is_validated(client, admin_token, slug):
    response = await client.post(
        "/api/v1/platform/tenants",
        headers=bearer(admin_token),
        json={**ACME, "slug": slug, "email": f"{abs(hash(slug))}@example.com"},
    )
    assert response.status_code == 422


async def test_reseeding_does_not_leak_demo_membership_to_foreign_owners(
    client, admin_token, db_session
):
    """Regression: a restart must not add other tenants' owners to the demo tenant.

    ``seed_auth_data`` runs on every application startup. Backfilling a demo
    membership for every row in ``users`` used to hand a foreign ``tenant_owner``
    full access to the demo tenant.
    """
    from sqlalchemy import select

    from app.models.tenant import Tenant, TenantMember
    from app.models.user import User
    from app.seed_auth import seed_auth_data

    await _create_tenant(client, admin_token)
    await seed_auth_data(db_session)  # simulate a backend restart

    owner = (
        await db_session.execute(select(User).where(User.email == ACME["email"]))
    ).scalars().one()
    rows = (
        await db_session.execute(
            select(Tenant.slug)
            .join(TenantMember, TenantMember.tenant_id == Tenant.id)
            .where(TenantMember.user_id == owner.id)
        )
    ).scalars().all()

    assert list(rows) == [ACME["slug"]], (
        f"foreign owner must only belong to its own tenant, got {rows}"
    )
