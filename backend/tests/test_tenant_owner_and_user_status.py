"""租户列表展示管理员（用户名/用户ID）+ 平台端启用/停用用户。"""

from __future__ import annotations

from tests.conftest import bearer


async def test_tenants_list_exposes_owner(client, platform_token):
    rows = (
        await client.get("/api/v1/platform/tenants-list", headers=bearer(platform_token))
    ).json()["data"]
    demo = next(row for row in rows if row["slug"] == "demo")
    assert demo["owner"] is not None, "租户列表必须带管理员信息"
    assert demo["owner"]["username"]
    assert demo["owner"]["public_id"].startswith("usr_")


async def test_platform_can_disable_and_enable_user(client, admin_token, platform_token):
    created = await client.post(
        "/api/v1/users",
        headers=bearer(admin_token),
        json={
            "username": "toggle_me",
            "nickname": "开关测试",
            "email": "toggle_me@example.com",
            "role": "viewer",
            "status": "active",
            "password": "Toggle@123456",
        },
    )
    assert created.status_code == 200, created.text
    user_id = created.json()["data"]["id"]

    disabled = await client.put(
        f"/api/v1/platform/users/{user_id}/status",
        headers=bearer(platform_token),
        json={"status": "disabled"},
    )
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["data"]["status"] == "disabled"

    enabled = await client.put(
        f"/api/v1/platform/users/{user_id}/status",
        headers=bearer(platform_token),
        json={"status": "active"},
    )
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["data"]["status"] == "active"


async def test_cannot_disable_platform_admin_or_self(client, platform_token):
    users = (
        await client.get("/api/v1/platform/users?pageSize=100", headers=bearer(platform_token))
    ).json()["data"]["list"]
    admin_user = next(row for row in users if row["is_platform_admin"])

    blocked = await client.put(
        f"/api/v1/platform/users/{admin_user['id']}/status",
        headers=bearer(platform_token),
        json={"status": "disabled"},
    )
    assert blocked.status_code == 400, blocked.text
    assert "平台账号" in blocked.json()["message"]


async def test_invalid_status_is_rejected(client, admin_token, platform_token):
    users = (
        await client.get("/api/v1/platform/users?pageSize=5", headers=bearer(platform_token))
    ).json()["data"]["list"]
    target = next(row for row in users if not row["is_platform_admin"])
    response = await client.put(
        f"/api/v1/platform/users/{target['id']}/status",
        headers=bearer(platform_token),
        json={"status": "banned"},
    )
    assert response.status_code == 400, response.text
