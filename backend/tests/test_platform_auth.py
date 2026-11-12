"""平台端 vs 租户端的认证隔离（本次架构拆分的红线）。

拆分目标：赛霄玄思 SaaS 管理平台只管租户与平台配置，租户控制台管业务。
两套账号不得互相越界，靠三件事保证：
  1. aud=platform vs aud=admin 的 JWT audience 校验；
  2. users.is_platform_admin 决定谁能登平台端；
  3. refresh cookie 分成两个名字，互不覆盖、互不通用。
"""

from __future__ import annotations

from tests.conftest import ADMIN_PASSWORD, PLATFORM_ADMIN_PASSWORD, bearer

PLATFORM_REFRESH_COOKIE = "sxxs_platform_refresh"


async def _platform_login(client) -> dict:
    response = await client.post(
        "/api/v1/platform/auth/login",
        json={"username": "root", "password": PLATFORM_ADMIN_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def test_platform_login_issues_platform_only_scope(client):
    data = await _platform_login(client)
    assert data["roles"] == ["platform_admin"]
    assert data["permissions"], "平台账号至少要拿到 platform:* 权限"
    assert all(code.startswith("platform:") for code in data["permissions"]), (
        "平台账号不应持有任何租户业务权限：" + repr(data["permissions"])
    )


async def test_platform_login_sets_its_own_refresh_cookie(client):
    response = await client.post(
        "/api/v1/platform/auth/login",
        json={"username": "root", "password": PLATFORM_ADMIN_PASSWORD},
    )
    cookie_header = response.headers.get("set-cookie", "")
    assert PLATFORM_REFRESH_COOKIE in cookie_header
    # 不能复用租户端的 cookie 名，否则开发环境两个前端会互相踢下线
    assert "antd_pro_refresh=" not in cookie_header


async def test_tenant_user_cannot_log_into_platform(client):
    response = await client.post(
        "/api/v1/platform/auth/login",
        json={"username": "admin", "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 403, response.text
    assert "平台管理员" in response.json()["message"]


async def test_platform_token_cannot_call_tenant_endpoints(client):
    data = await _platform_login(client)
    response = await client.get("/api/v1/auth/me", headers=bearer(data["access_token"]))
    assert response.status_code == 401, response.text


async def test_tenant_token_cannot_call_platform_endpoints(client, admin_token):
    response = await client.get("/api/v1/platform/tenants", headers=bearer(admin_token))
    assert response.status_code == 401, response.text


async def test_refresh_tokens_are_not_interchangeable(client, admin_token):
    # 平台 refresh cookie 去租户接口换 token：必须失败
    await _platform_login(client)
    platform_refresh = client.cookies.get(PLATFORM_REFRESH_COOKIE)
    assert platform_refresh
    response = await client.post(
        "/api/v1/auth/refresh",
        headers={"cookie": f"antd_pro_refresh={platform_refresh}"},
    )
    assert response.status_code == 401, response.text

    # 租户 refresh cookie 去平台接口换 token：同样必须失败
    tenant_refresh = client.cookies.get("antd_pro_refresh")
    assert tenant_refresh
    response = await client.post(
        "/api/v1/platform/auth/refresh",
        headers={"cookie": f"{PLATFORM_REFRESH_COOKIE}={tenant_refresh}"},
    )
    assert response.status_code == 401, response.text


async def test_platform_settings_roundtrip(client):
    data = await _platform_login(client)
    headers = bearer(data["access_token"])

    fetched = await client.get("/api/v1/platform/settings/platform", headers=headers)
    assert fetched.status_code == 200, fetched.text
    config = fetched.json()["data"]["config"]
    assert config["name"] == "赛霄玄思 SaaS 管理平台"

    updated = await client.put(
        "/api/v1/platform/settings/platform",
        headers=headers,
        json={"enabled": True, "config": {**config, "announcement": "平台维护已上线"}},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["config"]["announcement"] == "平台维护已上线"

    again = await client.get("/api/v1/platform/settings/platform", headers=headers)
    assert again.json()["data"]["config"]["announcement"] == "平台维护已上线"


async def test_platform_settings_unknown_category_is_404(client):
    data = await _platform_login(client)
    response = await client.get(
        "/api/v1/platform/settings/nope", headers=bearer(data["access_token"])
    )
    assert response.status_code == 404, response.text


async def test_platform_settings_reject_tenant_token(client, admin_token):
    response = await client.get("/api/v1/platform/settings/platform", headers=bearer(admin_token))
    assert response.status_code == 401, response.text
