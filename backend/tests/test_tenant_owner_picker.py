"""开通租户：直接从平台用户列表里选一个已有用户当管理员。"""

from __future__ import annotations

from sqlalchemy import select

from app.models.tenant import TenantMember
from tests.conftest import bearer


async def test_create_tenant_with_existing_owner(client, platform_token, db_session):
    users = (
        await client.get("/api/v1/platform/users?pageSize=100", headers=bearer(platform_token))
    ).json()["data"]["list"]
    owner = next(row for row in users if row["email"] == "lisi@example.com")

    created = await client.post(
        "/api/v1/platform/tenants",
        headers=bearer(platform_token),
        json={
            "name": "选人开通站",
            "slug": "picked-owner-market",
            "owner_user_id": owner["id"],
        },
    )
    assert created.status_code == 200, created.text

    # 成员关系已建立（lisi 因此会有两个租户，登录接口会要求选择租户，故直接查成员表）
    tenant_id = created.json()["data"]["id"]
    member = (
        await db_session.scalars(
            select(TenantMember).where(
                TenantMember.tenant_id == tenant_id,
                TenantMember.user_id == owner["id"],
            )
        )
    ).first()
    assert member is not None, "选中的用户必须成为该租户成员"
    assert member.status == "active"


async def test_create_tenant_requires_owner_or_credentials(client, platform_token):
    rejected = await client.post(
        "/api/v1/platform/tenants",
        headers=bearer(platform_token),
        json={"name": "缺管理员站", "slug": "no-owner-market"},
    )
    assert rejected.status_code == 422, rejected.text


async def test_create_tenant_with_unknown_owner_is_404(client, platform_token):
    response = await client.post(
        "/api/v1/platform/tenants",
        headers=bearer(platform_token),
        json={
            "name": "幽灵管理员站",
            "slug": "ghost-owner-market",
            "owner_user_id": 999999,
        },
    )
    assert response.status_code == 404, response.text
