"""租户控制台的角色管理边界（越权回归）。

`roles` 是全库共享表，但 `admin` / `platform_admin` / `platform_support`
只属于平台端。修复前的 `/api/v1/roles` 既不看租户、也不看角色归属：

* `GET /roles` 会列出全站 10 个角色（含平台管理员）；
* `GET|PUT /roles/{id}/permissions` 能读写**任意**角色的权限集；
* `PUT|DELETE /roles/{id}` 能改名、停用、删除平台角色。

后果不只是「看到全站内容」：租户给某个角色塞进 `platform:tenant:read`
之后，`services/audit.is_platform_viewer()` 就会放行，直接读到跨租户审计。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.role import Role
from app.services.role import PLATFORM_ROLE_CODES, _guard_permission_grants
from tests.conftest import bearer


async def _role_id(db, code: str) -> int:
    role_id = await db.scalar(select(Role.id).where(Role.code == code))
    assert role_id is not None, f"角色 {code} 不存在"
    return role_id


async def test_tenant_role_list_hides_platform_roles(client, admin_token):
    response = await client.get(
        "/api/v1/roles", headers=bearer(admin_token), params={"pageSize": 500}
    )
    assert response.status_code == 200, response.text
    codes = {row["code"] for row in response.json()["data"]["list"]}

    assert codes & PLATFORM_ROLE_CODES == set(), f"租户看到了平台角色：{codes & PLATFORM_ROLE_CODES}"
    # 业务角色必须仍在，否则租户没法管自己的角色
    assert "tenant_admin" in codes


async def test_tenant_cannot_read_or_write_platform_roles(client, admin_token, db_session):
    platform_admin_id = await _role_id(db_session, "platform_admin")
    super_id = await _role_id(db_session, "admin")

    read = await client.get(
        f"/api/v1/roles/{platform_admin_id}/permissions", headers=bearer(admin_token)
    )
    assert read.status_code == 403, read.text

    write = await client.put(
        f"/api/v1/roles/{platform_admin_id}/permissions",
        headers=bearer(admin_token),
        json={"permission_codes": ["platform:tenant:read"]},
    )
    assert write.status_code == 403, write.text

    rename = await client.put(
        f"/api/v1/roles/{super_id}",
        headers=bearer(admin_token),
        json={"name": "被租户改名"},
    )
    assert rename.status_code == 403, rename.text

    removed = await client.delete(f"/api/v1/roles/{super_id}", headers=bearer(admin_token))
    assert removed.status_code == 403, removed.text


async def test_platform_permission_cannot_be_granted_to_any_role(client, admin_token):
    """`admin` 自己持有 platform:* —— 子集校验会放行，只能靠平台权限硬规则拦住。"""
    created = await client.post(
        "/api/v1/roles",
        headers=bearer(admin_token),
        json={"code": "iso_probe_role", "name": "越权探针"},
    )
    assert created.status_code == 200, created.text
    role_id = created.json()["data"]["id"]

    try:
        response = await client.put(
            f"/api/v1/roles/{role_id}/permissions",
            headers=bearer(admin_token),
            json={"permission_codes": ["platform:tenant:read"]},
        )
        assert response.status_code == 403, response.text
        assert "platform:tenant:read" in response.text
    finally:
        await client.delete(f"/api/v1/roles/{role_id}", headers=bearer(admin_token))


async def test_tenant_can_still_manage_own_role_permissions(client, admin_token):
    created = await client.post(
        "/api/v1/roles",
        headers=bearer(admin_token),
        json={"code": "iso_ok_role", "name": "正常角色"},
    )
    assert created.status_code == 200, created.text
    role_id = created.json()["data"]["id"]

    try:
        response = await client.put(
            f"/api/v1/roles/{role_id}/permissions",
            headers=bearer(admin_token),
            json={"permission_codes": ["user:read", "user:write"]},
        )
        assert response.status_code == 200, response.text
        assert set(response.json()["data"]["selected"]) == {"user:read", "user:write"}
    finally:
        await client.delete(f"/api/v1/roles/{role_id}", headers=bearer(admin_token))


def test_guard_blocks_privilege_escalation():
    """授出自己没有的权限 → 403（`order:read:all` 可跨租户看订单）。"""
    context = SimpleNamespace(permissions={"user:read", "user:write"})
    with pytest.raises(HTTPException) as excinfo:
        _guard_permission_grants(context, ["user:read", "order:read:all"])

    assert excinfo.value.status_code == 403
    assert "order:read:all" in excinfo.value.detail


async def test_operator_without_role_manage_is_rejected(client, operator_token):
    response = await client.get("/api/v1/roles", headers=bearer(operator_token))
    assert response.status_code == 403, response.text
