"""Audit trail for the order / payment / settlement chain.

Covers plan §7.5 审计 and §18 #5 (platform admin may cross tenants, but every
action is auditable).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.catalog import Product, ProductSku
from app.models.seller import Seller
from app.models.tenant import Tenant
from tests.conftest import bearer


async def _sku(db_session) -> ProductSku:
    product = (
        await db_session.execute(
            select(Product).where(Product.tenant_id == 1, Product.status == "on_sale")
        )
    ).scalars().first()
    assert product is not None
    sku = (
        await db_session.execute(select(ProductSku).where(ProductSku.product_id == product.id))
    ).scalars().first()
    assert sku is not None
    return sku


async def _seller(db_session) -> Seller:
    seller = (
        await db_session.execute(
            select(Seller).where(Seller.tenant_id == 1, Seller.status == "active")
        )
    ).scalars().first()
    assert seller is not None
    return seller


async def _place_order(client, customer_token, db_session) -> int:
    sku = await _sku(db_session)
    response = await client.post(
        "/api/v1/portal/orders",
        headers=bearer(customer_token),
        json={
            "items": [{"sku_id": sku.id, "quantity": 1}],
            "receiver_name": "审计买家",
            "receiver_phone": "13900000000",
            "receiver_address": {"city": "深圳市", "detail": "审计路 1 号"},
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["id"]


async def _logs(client, admin_token, **params) -> list[dict]:
    response = await client.get(
        "/api/v1/audit-logs", headers=bearer(admin_token), params={"pageSize": 100, **params}
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["list"]


# --------------------------------------------------------------------------- #
# Order / payment chain
# --------------------------------------------------------------------------- #


async def test_creating_an_order_is_audited(client, admin_token, customer_token, db_session):
    order_id = await _place_order(client, customer_token, db_session)

    rows = await _logs(client, admin_token, action="order.created", target_id=order_id)
    assert rows, "order creation must produce an audit row"
    row = rows[0]
    assert row["target_type"] == "order"
    assert row["actor_id"] is not None
    assert row["after"]["seller_order_count"] >= 1
    assert row["after"]["payable_amount_cents"] > 0


async def test_payment_is_audited_with_before_after(
    client, admin_token, customer_token, db_session
):
    order_id = await _place_order(client, customer_token, db_session)
    await client.post(
        f"/api/v1/portal/orders/{order_id}/mock-pay", headers=bearer(customer_token)
    )

    rows = await _logs(client, admin_token, action="order.paid", target_id=order_id)
    assert rows, "payment must produce an audit row"
    row = rows[0]
    assert row["before"]["status"] == "pending_payment"
    assert row["after"]["status"] == "paid"
    assert row["after"]["amount_cents"] > 0


async def test_cancellation_is_audited(client, admin_token, customer_token, db_session):
    order_id = await _place_order(client, customer_token, db_session)
    await client.post(f"/api/v1/admin/orders/{order_id}/cancel", headers=bearer(admin_token))

    rows = await _logs(client, admin_token, action="order.cancelled", target_id=order_id)
    assert rows
    assert rows[0]["after"]["status"] == "cancelled"


async def test_ship_and_confirm_are_audited(
    client, admin_token, customer_token, db_session
):
    order_id = await _place_order(client, customer_token, db_session)
    await client.post(
        f"/api/v1/portal/orders/{order_id}/mock-pay", headers=bearer(customer_token)
    )

    from app.models.order import SellerOrder

    seller_order = (
        await db_session.execute(
            select(SellerOrder).where(SellerOrder.order_id == order_id)
        )
    ).scalars().first()
    assert seller_order is not None

    ship_response = await client.post(
        f"/api/v1/admin/seller-orders/{seller_order.id}/ship",
        headers=bearer(admin_token),
        json={"carrier": "顺丰速运", "tracking_no": "SF-AUDIT-1"},
    )
    assert ship_response.status_code == 200, ship_response.text
    shipped = await _logs(
        client, admin_token, action="seller_order.shipped", target_id=seller_order.id
    )
    assert shipped
    assert shipped[0]["after"]["carrier"] == "顺丰速运"

    await client.post(
        f"/api/v1/portal/orders/{order_id}/confirm", headers=bearer(customer_token)
    )
    confirmed = await _logs(client, admin_token, action="order.confirmed", target_id=order_id)
    assert confirmed
    assert confirmed[0]["after"]["status"] == "completed"


async def test_refund_is_audited(client, admin_token, customer_token, db_session):
    order_id = await _place_order(client, customer_token, db_session)
    await client.post(
        f"/api/v1/portal/orders/{order_id}/mock-pay", headers=bearer(customer_token)
    )

    from app.models.order import SellerOrder

    seller_order = (
        await db_session.execute(
            select(SellerOrder).where(SellerOrder.order_id == order_id)
        )
    ).scalars().first()

    response = await client.post(
        f"/api/v1/admin/seller-orders/{seller_order.id}/refund",
        headers=bearer(admin_token),
        json={"amount_cents": 100, "reason": "审计退款"},
    )
    assert response.status_code == 200, response.text

    rows = await _logs(
        client, admin_token, action="seller_order.refunded", target_id=seller_order.id
    )
    assert rows
    assert rows[0]["after"]["reason"] == "审计退款"


# --------------------------------------------------------------------------- #
# Finance & platform events
# --------------------------------------------------------------------------- #


async def test_payout_and_settlement_events_are_audited(
    client, admin_token, customer_token, db_session
):
    from app.models.order import SellerOrder

    seller = await _seller(db_session)
    tenant = await db_session.get(Tenant, 1)
    tenant.settlement_hold_days = 0

    order_id = await _place_order(client, customer_token, db_session)
    await client.post(
        f"/api/v1/portal/orders/{order_id}/mock-pay", headers=bearer(customer_token)
    )
    seller_order = (
        await db_session.execute(
            select(SellerOrder).where(SellerOrder.order_id == order_id)
        )
    ).scalars().first()
    seller_order.status = "completed"
    seller_order.completed_at = datetime.now(UTC)
    await db_session.flush()

    payout_id = (
        await client.post(
            f"/api/v1/admin/sellers/{seller.id}/payouts", headers=bearer(admin_token)
        )
    ).json()["data"]["id"]
    assert await _logs(client, admin_token, action="payout.requested", target_id=payout_id)

    await client.post(f"/api/v1/admin/payouts/{payout_id}/approve", headers=bearer(admin_token))
    assert await _logs(client, admin_token, action="payout.approved", target_id=payout_id)

    now = datetime.now(UTC)
    batch_id = (
        await client.post(
            "/api/v1/admin/settlement-batches",
            headers=bearer(admin_token),
            json={
                "period_start": (now - __import__("datetime").timedelta(days=1)).isoformat(),
                "period_end": (now + __import__("datetime").timedelta(days=1)).isoformat(),
            },
        )
    ).json()["data"]["id"]
    assert await _logs(
        client, admin_token, action="settlement_batch.created", target_id=batch_id
    )

    await client.post(
        f"/api/v1/admin/settlement-batches/{batch_id}/confirm", headers=bearer(admin_token)
    )
    await client.post(
        f"/api/v1/admin/settlement-batches/{batch_id}/pay", headers=bearer(admin_token)
    )
    assert await _logs(
        client, admin_token, action="settlement_batch.paid", target_id=batch_id
    )
    assert await _logs(client, admin_token, action="payout.paid", target_id=payout_id)


async def test_commission_rule_changes_are_audited(client, admin_token):
    created = (
        await client.post(
            "/api/v1/admin/commission-rules",
            headers=bearer(admin_token),
            json={"name": "审计佣金", "rate_bps": 700},
        )
    ).json()["data"]
    assert await _logs(
        client, admin_token, action="commission_rule.created", target_id=created["id"]
    )

    await client.put(
        f"/api/v1/admin/commission-rules/{created['id']}",
        headers=bearer(admin_token),
        json={"rate_bps": 900},
    )
    updated = await _logs(
        client, admin_token, action="commission_rule.updated", target_id=created["id"]
    )
    assert updated and updated[0]["before"]["rate_bps"] == 700
    assert updated[0]["after"]["rate_bps"] == 900

    await client.delete(
        f"/api/v1/admin/commission-rules/{created['id']}", headers=bearer(admin_token)
    )
    assert await _logs(
        client, admin_token, action="commission_rule.deleted", target_id=created["id"]
    )


async def test_tenant_suspend_and_resume_are_audited(client, admin_token, platform_token):
    created = (
        await client.post(
            "/api/v1/platform/tenants",
            headers=bearer(platform_token),
            json={
                "name": "Audit Tenant",
                "slug": "audit-tenant",
                "email": "audit-tenant@example.com",
                "nickname": "Audit",
                "password": "Audit@123456",
            },
        )
    ).json()["data"]

    await client.post(
        f"/api/v1/platform/tenants/{created['id']}/suspend",
        headers=bearer(platform_token),
        json={"reason": "审计停用"},
    )
    suspended = await _logs(
        client, admin_token, action="tenant.suspended", target_id=created["id"]
    )
    assert suspended
    assert suspended[0]["after"]["reason"] == "审计停用"

    await client.post(
        f"/api/v1/platform/tenants/{created['id']}/resume", headers=bearer(platform_token)
    )
    assert await _logs(client, admin_token, action="tenant.resumed", target_id=created["id"])


async def test_role_permission_change_is_audited(client, admin_token):
    roles = (await client.get("/api/v1/roles", headers=bearer(admin_token))).json()["data"]
    viewer = next(item for item in roles["list"] if item["code"] == "viewer")
    current = (
        await client.get(
            f"/api/v1/roles/{viewer['id']}/permissions", headers=bearer(admin_token)
        )
    ).json()["data"]

    await client.put(
        f"/api/v1/roles/{viewer['id']}/permissions",
        headers=bearer(admin_token),
        json={"permission_codes": current["selected"]},
    )
    rows = await _logs(
        client, admin_token, action="role.permissions_updated", target_id=viewer["id"]
    )
    assert rows
    assert "permission_codes" in rows[0]["after"]


async def test_im_moderation_is_audited(
    client, admin_token, customer_token, operator_token, db_session
):
    seller = await _seller(db_session)
    conversation_id = (
        await client.post(
            "/api/v1/im/conversations",
            headers=bearer(customer_token),
            json={"seller_id": seller.id},
        )
    ).json()["data"]["id"]
    message = (
        await client.post(
            f"/api/v1/im/conversations/{conversation_id}/messages",
            headers=bearer(customer_token),
            json={"content": "审计违规内容", "client_msg_id": "audit-im-1"},
        )
    ).json()["data"]

    report_id = (
        await client.post(
            f"/api/v1/im/messages/{message['id']}/report",
            headers=bearer(operator_token),
            json={"reason": "审计测试"},
        )
    ).json()["data"]["id"]
    await client.post(
        f"/api/v1/im/reports/{report_id}/handle",
        headers=bearer(admin_token),
        json={"action": "accept"},
    )

    rows = await _logs(
        client, admin_token, action="im.message.moderated", target_id=message["id"]
    )
    assert rows
    assert rows[0]["after"]["status"] == "moderated"


# --------------------------------------------------------------------------- #
# Audit trail access & isolation
# --------------------------------------------------------------------------- #


async def test_audit_rows_capture_ip_and_trace_id(client, admin_token, customer_token, db_session):
    await _place_order(client, customer_token, db_session)

    response = await client.get(
        "/api/v1/audit-logs",
        headers=bearer(admin_token),
        params={"action": "order.created", "pageSize": 5},
    )
    assert response.status_code == 200
    row = response.json()["data"]["list"][0]
    assert row["ip"], "audit rows must record the client IP"
    assert row["trace_id"], "audit rows must record a trace id for correlation"


async def test_trace_id_header_is_returned(client):
    response = await client.get("/health")
    assert response.headers.get("X-Trace-Id")


async def test_audit_log_pagination_and_shape(client, admin_token, customer_token, db_session):
    for _ in range(3):
        await _place_order(client, customer_token, db_session)

    response = await client.get(
        "/api/v1/audit-logs",
        headers=bearer(admin_token),
        params={"action": "order.created", "current": 1, "pageSize": 2},
    )
    data = response.json()["data"]
    assert data["pageSize"] == 2
    assert data["total"] >= 3
    assert len(data["list"]) == 2
    # Newest first.
    assert data["list"][0]["id"] > data["list"][1]["id"]


async def test_distinct_actions_endpoint(client, admin_token, customer_token, db_session):
    await _place_order(client, customer_token, db_session)
    response = await client.get("/api/v1/audit-logs/actions", headers=bearer(admin_token))
    assert response.status_code == 200
    assert "order.created" in response.json()["data"]


async def test_audit_is_tenant_scoped(client, admin_token, customer_token, db_session, platform_token):
    """A tenant owner must never read another tenant's audit rows."""
    await _place_order(client, customer_token, db_session)

    await client.post(
        "/api/v1/platform/tenants",
        headers=bearer(platform_token),
        json={
            "name": "Audit Other",
            "slug": "audit-other",
            "email": "audit-other@example.com",
            "nickname": "Other",
            "password": "Other@123456",
        },
    )
    other = (
        await client.post(
            "/api/v1/auth/login",
            json={"username": "audit-other@example.com", "password": "Other@123456"},
        )
    ).json()["data"]["access_token"]

    # tenant_owner has audit:read inside its own tenant.
    response = await client.get("/api/v1/audit-logs", headers=bearer(other))
    assert response.status_code == 200
    assert response.json()["data"]["total"] == 0, "tenant B must not see demo audit rows"

    rows = response.json()["data"]["list"]
    assert all(row["tenant_id"] != 1 for row in rows)


async def test_customer_cannot_read_the_audit_trail(client, customer_token):
    assert (
        await client.get("/api/v1/audit-logs", headers=bearer(customer_token))
    ).status_code == 403


async def test_operator_without_audit_read_is_forbidden(client, operator_token):
    """`operator` has no `audit:read` in the seeded catalogue."""
    response = await client.get("/api/v1/audit-logs", headers=bearer(operator_token))
    assert response.status_code == 403


async def test_audit_rows_are_written_atomically_with_the_change(
    client, admin_token, customer_token, db_session
):
    """A failed business call must not leave a stray audit row."""
    before = (
        await client.get("/api/v1/audit-logs", headers=bearer(admin_token), params={"pageSize": 1})
    ).json()["data"]["total"]

    # Cancel a non-existent order -> 404, no audit row.
    await client.post("/api/v1/admin/orders/9999999/cancel", headers=bearer(admin_token))

    after = (
        await client.get("/api/v1/audit-logs", headers=bearer(admin_token), params={"pageSize": 1})
    ).json()["data"]["total"]
    assert after == before


@pytest.mark.parametrize("action", ["order.created", "order.paid"])
async def test_actions_are_filterable(client, admin_token, customer_token, db_session, action):
    order_id = await _place_order(client, customer_token, db_session)
    if action == "order.paid":
        await client.post(
            f"/api/v1/portal/orders/{order_id}/mock-pay", headers=bearer(customer_token)
        )

    rows = await _logs(client, admin_token, action=action)
    assert rows
    assert all(row["action"] == action for row in rows)


async def test_audit_rows_exist_in_the_database(
    client, admin_token, customer_token, db_session
):
    order_id = await _place_order(client, customer_token, db_session)
    stored = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "order.created", AuditLog.target_id == str(order_id)
            )
        )
    ).scalars().all()
    assert stored, "the audit row must be persisted in the same transaction"
