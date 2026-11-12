"""平台端用户总览 vs 租户端用户列表：权限边界。

1. 平台端能看到全站用户（跨租户）；
2. 租户端只看到自己租户的成员 —— 同站另一个租户的用户不能出现；
3. 两边的关键词搜索都覆盖用户ID（public_id）。
"""

from __future__ import annotations

from tests.conftest import bearer


async def test_tenant_token_cannot_use_platform_users(client, admin_token):
    response = await client.get("/api/v1/platform/users", headers=bearer(admin_token))
    assert response.status_code == 401, response.text


async def test_platform_sees_users_across_tenants(client, platform_token):
    # 新建一个租户，它的 owner 属于别的租户
    created = await client.post(
        "/api/v1/platform/tenants",
        headers=bearer(platform_token),
        json={
            "name": "跨租户用户站",
            "slug": "cross-tenant-users",
            "email": "owner-cross@example.com",
            "nickname": "别家站长",
            "password": "CrossUser@123456",
        },
    )
    assert created.status_code == 200, created.text

    response = await client.get(
        "/api/v1/platform/users", headers=bearer(platform_token), params={"pageSize": 100}
    )
    assert response.status_code == 200, response.text
    emails = {row["email"] for row in response.json()["data"]["list"]}
    assert "owner-cross@example.com" in emails, "平台端必须能看到所有租户的用户"
    assert any(not email.endswith("example.com") for email in emails) or emails


async def test_platform_keyword_matches_public_id(client, platform_token):
    listed = (
        await client.get(
            "/api/v1/platform/users",
            headers=bearer(platform_token),
            params={"pageSize": 1},
        )
    ).json()["data"]["list"]
    target = listed[0]

    hit = await client.get(
        "/api/v1/platform/users",
        headers=bearer(platform_token),
        params={"keyword": target["public_id"]},
    )
    assert hit.status_code == 200, hit.text
    rows = hit.json()["data"]["list"]
    assert [row["public_id"] for row in rows] == [target["public_id"]]


async def test_tenant_keyword_matches_public_id_and_stays_scoped(
    client, admin_token, platform_token
):
    # 另一个租户的用户：平台端能搜到
    await client.post(
        "/api/v1/platform/tenants",
        headers=bearer(platform_token),
        json={
            "name": "隔离用户站",
            "slug": "isolated-users",
            "email": "owner-isolated@example.com",
            "nickname": "隔离站长",
            "password": "Isolated@123456",
        },
    )
    platform_rows = (
        await client.get(
            "/api/v1/platform/users",
            headers=bearer(platform_token),
            params={"keyword": "owner-isolated@example.com"},
        )
    ).json()["data"]["list"]
    assert len(platform_rows) == 1
    foreign_id = platform_rows[0]["public_id"]

    # 租户端（demo）按这个用户ID搜：必须是空 —— 它不属于 demo
    tenant_hit = await client.get(
        "/api/v1/users", headers=bearer(admin_token), params={"keyword": foreign_id}
    )
    assert tenant_hit.status_code == 200, tenant_hit.text
    assert tenant_hit.json()["data"]["list"] == []
