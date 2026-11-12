"""经营看板聚合接口 GET /api/v1/dashboard/overview.

Replaces the template's fake chart data with numbers computed from the real
business tables (orders / products / sellers / payouts / IM reports / plan
quotas).

Contract under test:

* tenant scoped: another tenant never sees the demo tenant's numbers
* money comes from PAID orders only; a pending_payment order is not revenue
* the daily trend is zero-filled and bucketed on the **business** time zone
  (Asia/Shanghai by default), not on UTC -- otherwise today's GMV looks wrong
  for eight hours of every day
* top products are ranked from real order items
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.models.catalog import Product, ProductSku
from tests.conftest import bearer

BUSINESS_TZ = ZoneInfo("Asia/Shanghai")


async def _sku(db_session) -> ProductSku:
    product = (
        (
            await db_session.execute(
                select(Product).where(Product.tenant_id == 1, Product.status == "on_sale")
            )
        )
        .scalars()
        .first()
    )
    assert product is not None
    sku = (
        (await db_session.execute(select(ProductSku).where(ProductSku.product_id == product.id)))
        .scalars()
        .first()
    )
    assert sku is not None
    return sku


async def _place_order(client, customer_token, db_session, quantity: int = 1) -> tuple[int, int]:
    """Create an unpaid portal order; returns (order_id, payable_cents)."""
    sku = await _sku(db_session)
    response = await client.post(
        "/api/v1/portal/orders",
        headers=bearer(customer_token),
        json={
            "items": [{"sku_id": sku.id, "quantity": quantity}],
            "receiver_name": "看板买家",
            "receiver_phone": "13900008888",
            "receiver_address": {"city": "深圳市", "detail": "看板路 1 号"},
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    return payload["id"], payload["payable_amount_cents"]


async def _overview(client, admin_token, **params) -> dict:
    response = await client.get(
        "/api/v1/dashboard/overview", headers=bearer(admin_token), params=params
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def test_overview_returns_the_documented_shape(client, admin_token):
    data = await _overview(client, admin_token)

    assert data["range"]["days"] == 30
    kpi = data["kpi"]
    for key in (
        "gmv_today_cents",
        "gmv_yesterday_cents",
        "orders_today",
        "orders_yesterday",
        "new_buyers_today",
        "pending_payment_orders",
        "products_on_sale",
        "products_pending_review",
        "sellers_active",
        "sellers_pending",
        "payouts_pending_count",
        "payouts_pending_cents",
        "im_reports_open",
    ):
        assert key in kpi, f"missing kpi field {key}"
        assert isinstance(kpi[key], int), f"{key} must be an int"

    assert len(data["trend"]) == 30
    assert set(data["trend"][0]) == {"date", "gmv_cents", "orders"}
    assert isinstance(data["order_status"], list)
    assert isinstance(data["top_products"], list)
    assert "plan" in data["usage"]


async def test_trend_is_zero_filled_and_ordered_by_business_day(client, admin_token):
    data = await _overview(client, admin_token, days=14)

    trend = data["trend"]
    assert len(trend) == 14
    dates = [row["date"] for row in trend]
    assert dates == sorted(dates), "trend must be ascending"
    assert dates[-1] == datetime.now(BUSINESS_TZ).date().isoformat(), (
        "the last bucket must be today in the business time zone"
    )
    assert all(row["gmv_cents"] >= 0 for row in trend)


async def test_paying_an_order_shows_up_in_today_gmv_and_orders(
    client, admin_token, customer_token, db_session
):
    before = await _overview(client, admin_token)
    order_id, amount = await _place_order(client, customer_token, db_session, quantity=2)

    pending = await _overview(client, admin_token)
    assert pending["kpi"]["pending_payment_orders"] == (before["kpi"]["pending_payment_orders"] + 1)
    assert pending["kpi"]["gmv_today_cents"] == before["kpi"]["gmv_today_cents"], (
        "an unpaid order must never count as revenue"
    )

    paid = await client.post(
        f"/api/v1/portal/orders/{order_id}/mock-pay", headers=bearer(customer_token)
    )
    assert paid.status_code == 200, paid.text

    after = await _overview(client, admin_token)
    assert after["kpi"]["gmv_today_cents"] == before["kpi"]["gmv_today_cents"] + amount
    assert after["kpi"]["orders_today"] == before["kpi"]["orders_today"] + 1
    assert after["trend"][-1]["gmv_cents"] == before["trend"][-1]["gmv_cents"] + amount


async def test_cancelled_order_does_not_count_as_revenue(
    client, admin_token, customer_token, db_session
):
    before = await _overview(client, admin_token)
    order_id, _amount = await _place_order(client, customer_token, db_session)
    cancelled = await client.post(
        f"/api/v1/portal/orders/{order_id}/cancel", headers=bearer(customer_token)
    )
    if cancelled.status_code == 404:
        pytest.skip("no buyer-facing cancel endpoint in this build")
    assert cancelled.status_code == 200, cancelled.text

    after = await _overview(client, admin_token)
    assert after["kpi"]["gmv_today_cents"] == before["kpi"]["gmv_today_cents"]
    assert after["kpi"]["pending_payment_orders"] == before["kpi"]["pending_payment_orders"]


async def test_order_status_distribution_matches_the_tenant(
    client, admin_token, customer_token, db_session
):
    await _place_order(client, customer_token, db_session)
    data = await _overview(client, admin_token)

    buckets = {row["status"]: row["count"] for row in data["order_status"]}
    assert buckets, "status distribution must not be empty"
    assert all(count > 0 for count in buckets.values()), "zero buckets must be dropped"
    assert data["totals"]["orders"] == sum(buckets.values())


async def test_top_products_come_from_real_order_items(
    client, admin_token, customer_token, db_session
):
    order_id, _amount = await _place_order(client, customer_token, db_session, quantity=3)
    await client.post(f"/api/v1/portal/orders/{order_id}/mock-pay", headers=bearer(customer_token))

    data = await _overview(client, admin_token)
    assert data["top_products"], "a paid order must produce a top product row"
    top = data["top_products"][0]
    assert set(top) == {"product_id", "name", "quantity", "gmv_cents"}
    assert top["quantity"] >= 3
    assert top["gmv_cents"] > 0


async def test_usage_block_reflects_the_plan(client, admin_token):
    data = await _overview(client, admin_token)
    usage = data["usage"]
    assert usage["plan"] == "pro"
    assert usage["products_used"] >= 1
    assert usage["products_quota"] == 5000
    assert usage["days_left"] is not None


async def test_overview_is_tenant_scoped(client, admin_token, platform_token):
    created = await client.post(
        "/api/v1/platform/tenants",
        headers=bearer(platform_token),
        json={
            "name": "Dashboard Other Tenant",
            "slug": "dash-other",
            "email": "dash-other@example.com",
            "nickname": "Other",
            "password": "Other@123456",
        },
    )
    assert created.status_code == 200, created.text
    other = (
        await client.post(
            "/api/v1/auth/login",
            json={"username": "dash-other@example.com", "password": "Other@123456"},
        )
    ).json()["data"]["access_token"]

    response = await client.get("/api/v1/dashboard/overview", headers=bearer(other))
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["totals"]["orders"] == 0, "a fresh tenant must not see demo orders"
    assert data["kpi"]["gmv_today_cents"] == 0
    assert data["top_products"] == []


async def test_customer_cannot_read_the_dashboard(client, customer_token):
    response = await client.get("/api/v1/dashboard/overview", headers=bearer(customer_token))
    assert response.status_code == 403


@pytest.mark.parametrize("days", [0, 6, 91])
async def test_days_parameter_is_bounded(client, admin_token, days):
    response = await client.get(
        "/api/v1/dashboard/overview",
        headers=bearer(admin_token),
        params={"days": days},
    )
    assert response.status_code == 422
