"""System health and authentication contract tests."""

from __future__ import annotations

import pytest

from tests.conftest import ADMIN_PASSWORD, DEMO_PASSWORD, bearer


async def test_health_returns_ok(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_login_rejects_wrong_password(client):
    response = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "wrong-password"}
    )
    assert response.status_code == 401
    assert response.json()["code"] == 401


async def test_login_returns_permissions_and_sets_refresh_cookie(client):
    response = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["token_type"] == "bearer"
    assert payload["expires_in"] > 0
    assert "user:read" in payload["permissions"]
    assert payload["current_tenant"]["slug"] == "demo"
    assert "admin" in payload["roles"]
    assert "antd_pro_refresh" in response.cookies


async def test_me_requires_token(client):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_me_rejects_garbage_token(client):
    response = await client.get("/api/v1/auth/me", headers=bearer("not-a-jwt"))
    assert response.status_code == 401


async def test_me_returns_identity_and_permission_version(client, admin_token):
    response = await client.get("/api/v1/auth/me", headers=bearer(admin_token))
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["user"]["username"] == "admin"
    assert data["permission_version"] >= 1
    assert data["tenants"], "admin must belong to at least one tenant"


async def test_refresh_rotates_the_token(client):
    login_response = await client.post(
        "/api/v1/auth/login", json={"username": "lisi", "password": DEMO_PASSWORD}
    )
    assert login_response.status_code == 200

    refreshed = await client.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["data"]["access_token"]


async def test_refresh_without_cookie_is_unauthorized(client):
    client.cookies.clear()
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 401


async def test_logout_invalidates_refresh_token(client):
    await client.post(
        "/api/v1/auth/login", json={"username": "lisi", "password": DEMO_PASSWORD}
    )
    assert (await client.post("/api/v1/auth/logout")).status_code == 200
    client.cookies.clear()
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401


async def test_register_creates_customer_with_minimal_permissions(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "tenant_slug": "demo",
            "email": "new-buyer@example.com",
            "nickname": "新买家",
            "password": "Buyer@123456",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert "customer" in data["roles"]
    assert "order:create" in data["permissions"]
    # A C-end customer must never receive back-office permissions.
    assert "user:write" not in data["permissions"]
    assert "role:manage" not in data["permissions"]
    assert "setting:payment" not in data["permissions"]


async def test_register_rejects_duplicate_email(client):
    payload = {
        "tenant_slug": "demo",
        "email": "duplicate@example.com",
        "nickname": "重复",
        "password": "Buyer@123456",
    }
    assert (await client.post("/api/v1/auth/register", json=payload)).status_code == 200
    duplicate = await client.post("/api/v1/auth/register", json=payload)
    assert duplicate.status_code == 409


async def test_register_rejects_unknown_tenant(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "tenant_slug": "does-not-exist",
            "email": "ghost@example.com",
            "nickname": "幽灵",
            "password": "Buyer@123456",
        },
    )
    assert response.status_code == 404


@pytest.mark.parametrize("path", ["/api/v1/users", "/api/v1/roles", "/api/v1/departments"])
async def test_protected_endpoints_require_authentication(client, path):
    response = await client.get(path)
    assert response.status_code == 401, f"{path} must not be readable anonymously"


async def test_disabled_user_cannot_log_in(client):
    """`zhaoliu` is seeded as a disabled account and must stay locked out."""
    response = await client.post(
        "/api/v1/auth/login", json={"username": "zhaoliu", "password": DEMO_PASSWORD}
    )
    assert response.status_code == 403
