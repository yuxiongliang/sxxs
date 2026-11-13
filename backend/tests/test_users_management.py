"""User, department and role management contracts.

Covers the tenant-membership side effects documented in the SiYuan changelog
entries "Phase 4：用户列表与租户成员" and "Phase 4：用户角色/删除同步 tenant 成员".
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.models.permission import MemberRole
from app.models.tenant import TenantMember
from app.models.user import User
from tests.conftest import bearer


async def test_list_users_is_paginated(client, admin_token):
    response = await client.get(
        "/api/v1/users", params={"current": 1, "pageSize": 5}, headers=bearer(admin_token)
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["current"] == 1
    assert data["pageSize"] == 5
    assert data["total"] >= 4
    assert len(data["list"]) <= 5
    # Password hashes must never leave the API.
    assert all("password" not in str(item.keys()).lower() for item in data["list"])


async def test_create_user_creates_tenant_membership_and_role(
    client, admin_token, db_session
):
    response = await client.post(
        "/api/v1/users",
        headers=bearer(admin_token),
        json={
            "username": "pytest_created",
            "nickname": "测试账号",
            "email": "pytest_created@example.com",
            "role": "viewer",
            "status": "active",
            "password": "Pytest@123456",
        },
    )
    assert response.status_code == 200, response.text
    created = response.json()["data"]

    members = (
        await db_session.execute(
            select(TenantMember).where(TenantMember.user_id == created["id"])
        )
    ).scalars().all()
    assert len(members) == 1
    role_links = (
        await db_session.execute(
            select(MemberRole).where(MemberRole.member_id == members[0].id)
        )
    ).scalars().all()
    assert len(role_links) == 1


async def test_update_user_role_keeps_member_roles_in_sync(
    client, admin_token, db_session
):
    created = (
        await client.post(
            "/api/v1/users",
            headers=bearer(admin_token),
            json={
                "username": "pytest_rolechange",
                "password": "Pytest@123456",
                "nickname": "角色变更",
                "email": "pytest_rolechange@example.com",
                "role": "viewer",
            },
        )
    ).json()["data"]

    response = await client.put(
        f"/api/v1/users/{created['id']}",
        headers=bearer(admin_token),
        json={"role": "operator"},
    )
    assert response.status_code == 200, response.text

    member = (
        await db_session.execute(
            select(TenantMember).where(TenantMember.user_id == created["id"])
        )
    ).scalars().first()
    assert member is not None
    links = (
        await db_session.execute(select(MemberRole).where(MemberRole.member_id == member.id))
    ).scalars().all()
    assert len(links) == 1


async def test_delete_user_removes_tenant_membership(client, admin_token, db_session):
    created = (
        await client.post(
            "/api/v1/users",
            headers=bearer(admin_token),
            json={
                "username": "pytest_delete",
                "password": "Pytest@123456",
                "nickname": "待删除",
                "email": "pytest_delete@example.com",
                "role": "viewer",
            },
        )
    ).json()["data"]

    response = await client.delete(
        f"/api/v1/users/{created['id']}", headers=bearer(admin_token)
    )
    assert response.status_code == 200, response.text

    remaining = (
        await db_session.execute(
            select(func.count(TenantMember.id)).where(
                TenantMember.user_id == created["id"]
            )
        )
    ).scalar_one()
    assert remaining == 0
    assert (await db_session.get(User, created["id"])) is None


async def test_reset_password_sets_a_working_password(client, admin_token):
    created = (
        await client.post(
            "/api/v1/users",
            headers=bearer(admin_token),
            json={
                "username": "pytest_reset",
                "password": "Pytest@123456",
                "nickname": "重置密码",
                "email": "pytest_reset@example.com",
                "role": "viewer",
            },
        )
    ).json()["data"]

    response = await client.post(
        f"/api/v1/users/{created['id']}/reset-password",
        headers=bearer(admin_token),
    )
    assert response.status_code == 200, response.text
    generated = response.json()["data"]["password"]

    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "pytest_reset", "password": generated},
    )
    assert login.status_code == 200, login.text


async def test_department_crud_roundtrip(client, admin_token):
    created = await client.post(
        "/api/v1/departments",
        headers=bearer(admin_token),
        json={"name": "pytest部门", "status": "active", "sort": 99},
    )
    assert created.status_code == 200, created.text
    department_id = created.json()["data"]["id"]

    updated = await client.put(
        f"/api/v1/departments/{department_id}",
        headers=bearer(admin_token),
        json={"name": "pytest部门改", "status": "active", "sort": 98},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["name"] == "pytest部门改"

    deleted = await client.delete(
        f"/api/v1/departments/{department_id}", headers=bearer(admin_token)
    )
    assert deleted.status_code == 200


async def test_role_permission_editing_bumps_permission_version(client, admin_token):
    before = (await client.get("/api/v1/auth/me", headers=bearer(admin_token))).json()["data"]
    # 系统内置角色已是全租户共享只读，改用本租户自建角色验证版本号自增。
    created = await client.post(
        "/api/v1/roles",
        headers=bearer(admin_token),
        json={"code": "version_probe_role", "name": "版本探针"},
    )
    assert created.status_code == 200, created.text
    role_id = created.json()["data"]["id"]

    current = (
        await client.get(f"/api/v1/roles/{role_id}/permissions", headers=bearer(admin_token))
    ).json()["data"]
    assert "all" in current and "selected" in current

    response = await client.put(
        f"/api/v1/roles/{role_id}/permissions",
        headers=bearer(admin_token),
        json={"permission_codes": ["user:read"]},
    )
    assert response.status_code == 200, response.text

    after = (await client.get("/api/v1/auth/me", headers=bearer(admin_token))).json()["data"]
    assert after["permission_version"] >= before["permission_version"]


@pytest.mark.parametrize("payload", [{"username": "x"}, {"nickname": "x"}])
async def test_create_user_validates_required_fields(client, admin_token, payload):
    response = await client.post(
        "/api/v1/users", headers=bearer(admin_token), json=payload
    )
    assert response.status_code == 422


async def test_role_change_invalidates_cached_permissions(client, admin_token):
    """A role change must take effect immediately, not after the cache TTL.

    ``AuthContext.permissions`` is cached in Redis for 60s under a key that
    embeds ``tenant.permission_version``. Changing a user's role has to bump that
    version, otherwise a demoted user keeps their privileges for up to a minute.
    """
    created = (
        await client.post(
            "/api/v1/users",
            headers=bearer(admin_token),
            json={
                "username": "pytest_cache_invalidate",
                "nickname": "缓存失效",
                "email": "pytest_cache_invalidate@example.com",
                "role": "viewer",
                "password": "Cache@123456",
            },
        )
    ).json()["data"]

    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "pytest_cache_invalidate", "password": "Cache@123456"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["data"]["access_token"]

    # Prime the Redis permission cache.
    before = (await client.get("/api/v1/auth/me", headers=bearer(token))).json()["data"]
    assert "order:manage" not in before["permissions"]

    promote = await client.put(
        f"/api/v1/users/{created['id']}",
        headers=bearer(admin_token),
        json={"role": "operator"},
    )
    assert promote.status_code == 200, promote.text

    after = (await client.get("/api/v1/auth/me", headers=bearer(token))).json()["data"]
    assert "order:manage" in after["permissions"], (
        "cached permissions were not invalidated by the role change"
    )
    assert after["permission_version"] > before["permission_version"]
