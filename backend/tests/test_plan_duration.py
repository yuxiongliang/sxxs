"""套餐「时长（月）」与删除规则。

1. duration_months 决定订阅窗口（N × 30 天）；
2. 被订阅引用的套餐不能删（409），未使用的可以真删；
3. 买断/档期套餐不能带试用（422）。
"""

from __future__ import annotations

from datetime import datetime

from tests.conftest import bearer


async def _create_plan(client, token, **overrides):
    payload = {"code": "months-plan", "name": "包月套餐", "price_cents": 10000, "period": "monthly"}
    payload.update(overrides)
    return await client.post("/api/v1/platform/plans", headers=bearer(token), json=payload)


async def test_duration_months_drives_the_subscription_window(client, platform_token):
    created = await _create_plan(client, platform_token, duration_months=12)
    assert created.status_code == 200, created.text
    plan_id = created.json()["data"]["id"]
    assert created.json()["data"]["duration_months"] == 12

    tenant = await client.post(
        "/api/v1/platform/tenants",
        headers=bearer(platform_token),
        json={
            "name": "时长测试站",
            "slug": "duration-market",
            "email": "owner-duration@example.com",
            "nickname": "站长",
            "password": "Duration@123456",
        },
    )
    tenant_id = tenant.json()["data"]["id"]
    subscribed = await client.post(
        f"/api/v1/platform/tenants/{tenant_id}/subscription",
        headers=bearer(platform_token),
        json={"plan_id": plan_id},
    )
    assert subscribed.status_code == 200, subscribed.text

    report = (
        await client.get(
            f"/api/v1/platform/tenants/{tenant_id}/usage", headers=bearer(platform_token)
        )
    ).json()["data"]
    start = datetime.fromisoformat(report["subscription"]["current_period_start"])
    end = datetime.fromisoformat(report["subscription"]["current_period_end"])
    assert (end - start).days == 12 * 30


async def test_plan_in_use_cannot_be_deleted(client, platform_token):
    created = await _create_plan(client, platform_token, code="in-use-plan", duration_months=1)
    plan_id = created.json()["data"]["id"]
    tenant = await client.post(
        "/api/v1/platform/tenants",
        headers=bearer(platform_token),
        json={
            "name": "删除测试站",
            "slug": "delete-market",
            "email": "owner-delete@example.com",
            "nickname": "站长",
            "password": "Delete@123456",
        },
    )
    tenant_id = tenant.json()["data"]["id"]
    await client.post(
        f"/api/v1/platform/tenants/{tenant_id}/subscription",
        headers=bearer(platform_token),
        json={"plan_id": plan_id},
    )

    blocked = await client.delete(
        f"/api/v1/platform/plans/{plan_id}", headers=bearer(platform_token)
    )
    assert blocked.status_code == 409, blocked.text
    assert "下架" in blocked.json()["message"]


async def test_unused_plan_can_be_deleted(client, platform_token):
    created = await _create_plan(client, platform_token, code="spare-plan")
    plan_id = created.json()["data"]["id"]
    removed = await client.delete(
        f"/api/v1/platform/plans/{plan_id}", headers=bearer(platform_token)
    )
    assert removed.status_code == 200, removed.text
    listed = (await client.get("/api/v1/platform/plans", headers=bearer(platform_token))).json()[
        "data"
    ]
    assert all(plan["id"] != plan_id for plan in listed)


async def test_buyout_plan_rejects_trial_days(client, platform_token):
    rejected = await _create_plan(
        client,
        platform_token,
        code="trial-buyout",
        period="lifetime",
        trial_days=14,
    )
    assert rejected.status_code == 422, rejected.text
