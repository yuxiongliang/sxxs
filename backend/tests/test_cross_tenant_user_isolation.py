"""租户 A ↔ 租户 B 的横向隔离（越权回归）。

`users` 表是全库共享的：一个 User 可以通过 `tenant_members` 同时属于多个租户。
修复前 `/api/v1/users/{id}` 系列接口只按 id 取用户、不看调用者属于哪个租户：

* `PUT    /users/{id}`              改任意用户（含 `password` 字段 → 改密码即接管账号，
  平台端的 `root` 也是一个 User 行）；
* `POST   /users/{id}/reset-password` 无租户参数，直接把**任意账号**密码重置成明文并返回；
* `DELETE /users/{id}`               会删掉全局 users 行，把别的租户的账号一并销毁。

修复后：非本租户成员一律 404（不泄露该 id 是否存在）。
"""

from __future__ import annotations

from tests.conftest import bearer, login

PASSWORD = "CrossTenant@123456"


async def _new_tenant(client, platform_token, slug: str) -> tuple[int, str]:
    email = f"owner@{slug}.example.com"
    created = await client.post(
        "/api/v1/platform/tenants",
        headers=bearer(platform_token),
        json={
            "name": f"{slug} 站",
            "slug": slug,
            "email": email,
            "nickname": f"{slug} 管理员",
            "password": PASSWORD,
        },
    )
    assert created.status_code == 200, created.text
    token = (await login(client, email, PASSWORD))["access_token"]
    return created.json()["data"]["id"], token


async def test_user_list_and_write_are_tenant_scoped(client, platform_token):
    _, token_a = await _new_tenant(client, platform_token, "iso-a")
    _, token_b = await _new_tenant(client, platform_token, "iso-b")

    created = await client.post(
        "/api/v1/users",
        headers=bearer(token_a),
        json={
            "username": "iso-a-staff",
            "nickname": "A 站员工",
            "email": "iso-a-staff@example.com",
            "role": "viewer",
            "password": "StaffA@123456",
        },
    )
    assert created.status_code == 200, created.text
    victim_id = created.json()["data"]["id"]

    # 1) 列表隔离
    listing = await client.get("/api/v1/users?pageSize=100", headers=bearer(token_b))
    assert listing.status_code == 200, listing.text
    emails = {row["email"] for row in listing.json()["data"]["list"]}
    assert "iso-a-staff@example.com" not in emails, "B 站不该看到 A 站的用户"

    # 2) 改：跨租户必须 404
    updated = await client.put(
        f"/api/v1/users/{victim_id}",
        headers=bearer(token_b),
        json={"nickname": "被 B 站改名"},
    )
    assert updated.status_code == 404, updated.text

    # 3) 重置密码：跨租户必须 404（这条最致命，会直接接管账号）
    reset = await client.post(
        f"/api/v1/users/{victim_id}/reset-password", headers=bearer(token_b)
    )
    assert reset.status_code == 404, reset.text

    # 4) 删：跨租户必须 404，且 A 站用户仍然在
    removed = await client.delete(f"/api/v1/users/{victim_id}", headers=bearer(token_b))
    assert removed.status_code == 404, removed.text

    still_there = await client.get("/api/v1/users?pageSize=100", headers=bearer(token_a))
    assert "iso-a-staff@example.com" in {row["email"] for row in still_there.json()["data"]["list"]}


async def test_platform_role_cannot_be_assigned_to_tenant_member(client, platform_token):
    _, token = await _new_tenant(client, platform_token, "iso-role")

    created = await client.post(
        "/api/v1/users",
        headers=bearer(token),
        json={
            "username": "iso-role-staff",
            "nickname": "提权探针",
            "email": "iso-role-staff@example.com",
            "role": "viewer",
            "password": "StaffR@123456",
        },
    )
    assert created.status_code == 200, created.text
    user_id = created.json()["data"]["id"]

    for role_code in ("platform_admin", "admin"):
        response = await client.put(
            f"/api/v1/users/{user_id}",
            headers=bearer(token),
            json={"role": role_code},
        )
        assert response.status_code == 400, response.text
        assert "平台角色" in response.text


async def test_own_tenant_user_can_still_be_managed(client, platform_token):
    """修复不能把正常管理也一起堵死。"""
    _, token = await _new_tenant(client, platform_token, "iso-own")

    created = await client.post(
        "/api/v1/users",
        headers=bearer(token),
        json={
            "username": "iso-own-staff",
            "nickname": "本租户员工",
            "email": "iso-own-staff@example.com",
            "role": "viewer",
            "password": "StaffO@123456",
        },
    )
    assert created.status_code == 200, created.text
    user_id = created.json()["data"]["id"]

    updated = await client.put(
        f"/api/v1/users/{user_id}", headers=bearer(token), json={"nickname": "改好了"}
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["nickname"] == "改好了"

    reset = await client.post(
        f"/api/v1/users/{user_id}/reset-password", headers=bearer(token)
    )
    assert reset.status_code == 200, reset.text
    assert reset.json()["data"]["password"].startswith("Antd@")
