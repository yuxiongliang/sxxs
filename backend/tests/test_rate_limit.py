"""Rate limiting contract tests.

The limiter is disabled globally in ``conftest.py`` (it would otherwise make the
rest of the suite depend on request volume). Each test here turns it back on with
a tight budget and asserts the observable behaviour.
"""

from __future__ import annotations

import pytest

from app.core.config import settings
from tests.conftest import ADMIN_PASSWORD, bearer


@pytest.fixture
def strict_limits(monkeypatch):
    """Enable limiting with a very small budget."""
    monkeypatch.setattr(settings, "rate_limit_enabled", True, raising=False)
    monkeypatch.setattr(settings, "rate_limit_requests", 3, raising=False)
    monkeypatch.setattr(settings, "rate_limit_window_seconds", 60, raising=False)
    monkeypatch.setattr(settings, "rate_limit_auth_requests", 2, raising=False)
    monkeypatch.setattr(settings, "rate_limit_auth_window_seconds", 60, raising=False)
    yield


async def test_global_limit_returns_429(client, admin_token, strict_limits):
    headers = bearer(admin_token)
    statuses = []
    for _ in range(6):
        response = await client.get("/api/v1/roles", headers=headers)
        statuses.append(response.status_code)

    assert 200 in statuses
    assert 429 in statuses, f"expected a 429 once the budget is spent, got {statuses}"

    limited = await client.get("/api/v1/roles", headers=headers)
    assert limited.status_code == 429
    body = limited.json()
    assert body["code"] == 429
    assert body["data"]["limit"] == 3
    assert "Retry-After" in limited.headers


async def test_auth_endpoints_use_the_tighter_budget(client, strict_limits):
    payload = {"username": "admin", "password": ADMIN_PASSWORD}
    statuses = []
    for _ in range(5):
        response = await client.post("/api/v1/auth/login", json=payload)
        statuses.append(response.status_code)

    assert statuses[0] == 200
    assert 429 in statuses, f"login should hit its own tighter budget, got {statuses}"


async def test_health_is_never_rate_limited(client, strict_limits):
    for _ in range(20):
        response = await client.get("/health")
        assert response.status_code == 200


async def test_successful_response_exposes_budget_headers(client, admin_token, strict_limits):
    response = await client.get("/api/v1/roles", headers=bearer(admin_token))
    assert response.status_code == 200
    assert response.headers["X-RateLimit-Limit"] == "3"
    assert int(response.headers["X-RateLimit-Remaining"]) >= 0


async def test_limiter_is_inert_when_disabled(client, admin_token, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", False, raising=False)
    for _ in range(10):
        response = await client.get("/api/v1/roles", headers=bearer(admin_token))
        assert response.status_code == 200


async def test_limited_request_never_reaches_the_handler(client, monkeypatch):
    """A rejected request must not execute the endpoint (no side effects)."""
    monkeypatch.setattr(settings, "rate_limit_enabled", True, raising=False)
    monkeypatch.setattr(settings, "rate_limit_auth_requests", 1, raising=False)
    monkeypatch.setattr(settings, "rate_limit_auth_window_seconds", 60, raising=False)

    first = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "wrong-password"},
    )
    assert first.status_code == 401, "the first attempt still reaches the handler"

    # Budget is spent; even correct credentials must be refused before auth runs.
    blocked = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": ADMIN_PASSWORD},
    )
    assert blocked.status_code == 429
    assert "access_token" not in blocked.text
    assert "antd_pro_refresh" not in blocked.cookies
