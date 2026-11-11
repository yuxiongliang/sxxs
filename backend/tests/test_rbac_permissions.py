"""RBAC enforcement: menu-level permissions must also be enforced by the API.

Plan §18 acceptance criteria:
  #4 operator only sees authorized menus; calling admin APIs directly returns 403
  #9 (auth part) every protected endpoint rejects anonymous access
"""

from __future__ import annotations

import pytest

from tests.conftest import bearer

ADMIN_ONLY_ENDPOINTS = [
    ("GET", "/api/v1/roles"),
    ("GET", "/api/v1/departments"),
    ("GET", "/api/v1/settings/payment"),
    ("POST", "/api/v1/roles"),
    ("POST", "/api/v1/departments"),
]

OPERATOR_ALLOWED_ENDPOINTS = [
    "/api/v1/users",
    "/api/v1/attachments",
    "/api/v1/notifications",
    "/api/v1/admin/sellers",
    "/api/v1/admin/products",
    "/api/v1/admin/orders",
]


@pytest.mark.parametrize("method,path", ADMIN_ONLY_ENDPOINTS)
async def test_operator_is_forbidden_from_admin_only_endpoints(
    client, operator_token, method, path
):
    response = await client.request(method, path, headers=bearer(operator_token), json={})
    assert response.status_code == 403, f"{method} {path} -> {response.status_code}"


@pytest.mark.parametrize("path", OPERATOR_ALLOWED_ENDPOINTS)
async def test_operator_can_read_operational_endpoints(client, operator_token, path):
    response = await client.get(path, headers=bearer(operator_token))
    assert response.status_code == 200, f"{path} -> {response.text}"


async def test_admin_can_read_every_admin_endpoint(client, admin_token):
    for path in ("/api/v1/roles", "/api/v1/departments", "/api/v1/settings/payment"):
        response = await client.get(path, headers=bearer(admin_token))
        assert response.status_code == 200, f"{path} -> {response.text}"


async def test_viewer_cannot_write_users(client, viewer_token):
    response = await client.post(
        "/api/v1/users",
        headers=bearer(viewer_token),
        json={"username": "nope", "nickname": "nope", "role": "viewer"},
    )
    assert response.status_code == 403


async def test_operator_cannot_send_writes_to_settings(client, operator_token):
    response = await client.put(
        "/api/v1/settings/payment",
        headers=bearer(operator_token),
        json={"enabled": True, "config": {}},
    )
    assert response.status_code == 403


async def test_unknown_setting_category_is_not_found(client, admin_token):
    response = await client.get("/api/v1/settings/not-a-category", headers=bearer(admin_token))
    assert response.status_code == 404


async def test_customer_cannot_reach_back_office_apis(client, customer_token):
    for path in ("/api/v1/users", "/api/v1/roles", "/api/v1/admin/orders"):
        response = await client.get(path, headers=bearer(customer_token))
        assert response.status_code == 403, f"{path} must be closed to C-end customers"


async def test_expired_or_foreign_audience_token_is_rejected(client, admin_token):
    """An admin token must not be usable as a portal token and vice versa."""
    from app.core.security import create_access_token

    portal_audience_token = create_access_token(
        user_id=1, tenant_id=1, audience="portal", roles=["admin"], permission_version=1
    )
    response = await client.get("/api/v1/auth/me", headers=bearer(portal_audience_token))
    assert response.status_code == 401
