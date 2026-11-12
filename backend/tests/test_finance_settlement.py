"""Commission rules, 账期 (settlement hold), payout review and settlement batches.

Plan §18 acceptance criteria covered:
  #6 order pricing/commission is decided server-side
  #8 commission / refund / settlement / payout balances stay reconcilable
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.catalog import Product, ProductSku
from app.models.finance import CommissionRule
from app.models.order import Order, SellerOrder
from app.models.seller import Seller
from app.models.tenant import Tenant
from tests.conftest import bearer


async def _seller(db_session, tenant_id: int = 1) -> Seller:
    seller = (
        await db_session.execute(
            select(Seller).where(Seller.tenant_id == tenant_id, Seller.status == "active")
        )
    ).scalars().first()
    assert seller is not None
    return seller


async def _sku(db_session) -> tuple[Product, ProductSku]:
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
    return product, sku


async def _place_and_pay(client, customer_token, db_session, quantity: int = 1) -> Order:
    _product, sku = await _sku(db_session)
    order_id = (
        await client.post(
            "/api/v1/portal/orders",
            headers=bearer(customer_token),
            json={
                "items": [{"sku_id": sku.id, "quantity": quantity}],
                "receiver_name": "佣金测试",
                "receiver_phone": "13900001111",
                "receiver_address": {"city": "深圳市", "detail": "测试路 1 号"},
            },
        )
    ).json()["data"]["id"]
    await client.post(
        f"/api/v1/portal/orders/{order_id}/mock-pay", headers=bearer(customer_token)
    )
    order = await db_session.get(Order, order_id)
    assert order is not None
    return order


async def _preview(client, admin_token, payload: dict) -> dict:
    response = await client.post(
        "/api/v1/admin/commission-rules/preview",
        headers=bearer(admin_token),
        json=payload,
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def _complete(db_session, order: Order) -> None:
    seller_order = (
        await db_session.execute(
            select(SellerOrder).where(SellerOrder.order_id == order.id)
        )
    ).scalars().first()
    assert seller_order is not None
    seller_order.status = "completed"
    seller_order.completed_at = datetime.now(UTC)
    await db_session.flush()


# --------------------------------------------------------------------------- #
# Commission rules
# --------------------------------------------------------------------------- #


async def test_default_commission_rule_is_seeded(client, admin_token):
    response = await client.get("/api/v1/admin/commission-rules", headers=bearer(admin_token))
    assert response.status_code == 200, response.text
    rules = response.json()["data"]
    assert any(rule["seller_id"] is None and rule["category_id"] is None for rule in rules)


async def test_commission_preview_uses_default_rate(client, admin_token):
    response = await client.post(
        "/api/v1/admin/commission-rules/preview",
        headers=bearer(admin_token),
        json={"subtotal_cents": 10000},
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["rate_bps"] == 1000
    assert data["commission_cents"] == 1000
    assert data["payable_to_seller_cents"] == 9000


async def test_seller_specific_rule_overrides_the_default(
    client, admin_token, customer_token, db_session
):
    seller = await _seller(db_session)
    created = await client.post(
        "/api/v1/admin/commission-rules",
        headers=bearer(admin_token),
        json={
            "name": "测试卖家专享 2%",
            "seller_id": seller.id,
            "rate_bps": 200,
            "priority": 10,
        },
    )
    assert created.status_code == 200, created.text

    preview = await _preview(client, admin_token, {"seller_id": seller.id, "subtotal_cents": 10000})
    assert preview["rate_bps"] == 200
    assert preview["commission_cents"] == 200

    # The order pipeline must use the same rule, not a hardcoded 10%.
    order = await _place_and_pay(client, customer_token, db_session)
    seller_order = (
        await db_session.execute(
            select(SellerOrder).where(SellerOrder.order_id == order.id)
        )
    ).scalars().first()
    assert seller_order is not None
    expected = seller_order.goods_amount_cents * 200 // 10_000
    assert seller_order.commission_amount_cents == expected


async def test_fixed_fee_is_added_to_the_rate(client, admin_token):
    created = await client.post(
        "/api/v1/admin/commission-rules",
        headers=bearer(admin_token),
        json={"name": "固定费规则", "rate_bps": 500, "fixed_fee_cents": 300, "priority": 5},
    )
    assert created.status_code == 200, created.text

    preview = await _preview(client, admin_token, {"subtotal_cents": 10000})
    assert preview["commission_cents"] == 500 + 300


async def test_disabled_rule_is_ignored(client, admin_token):
    created = await client.post(
        "/api/v1/admin/commission-rules",
        headers=bearer(admin_token),
        json={"name": "停用规则", "rate_bps": 9999, "priority": 99, "status": "disabled"},
    )
    assert created.status_code == 200

    preview = await _preview(client, admin_token, {"subtotal_cents": 10000})
    assert preview["rate_bps"] == 1000, "a disabled rule must never be applied"


async def test_rule_crud_roundtrip(client, admin_token):
    created = (
        await client.post(
            "/api/v1/admin/commission-rules",
            headers=bearer(admin_token),
            json={"name": "待改规则", "rate_bps": 800},
        )
    ).json()["data"]

    updated = await client.put(
        f"/api/v1/admin/commission-rules/{created['id']}",
        headers=bearer(admin_token),
        json={"rate_bps": 1200, "name": "已改规则"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["rate_bps"] == 1200

    deleted = await client.delete(
        f"/api/v1/admin/commission-rules/{created['id']}", headers=bearer(admin_token)
    )
    assert deleted.status_code == 200
    remaining = (
        await client.get("/api/v1/admin/commission-rules", headers=bearer(admin_token))
    ).json()["data"]
    assert all(rule["id"] != created["id"] for rule in remaining)


@pytest.mark.parametrize("payload", [{"rate_bps": 0, "fixed_fee_cents": 0}, {"rate_bps": -1}])
async def test_invalid_commission_rule_is_rejected(client, admin_token, payload):
    response = await client.post(
        "/api/v1/admin/commission-rules", headers=bearer(admin_token), json=payload
    )
    assert response.status_code in {400, 422}


async def test_operator_cannot_manage_commission_rules(client, operator_token):
    response = await client.post(
        "/api/v1/admin/commission-rules",
        headers=bearer(operator_token),
        json={"name": "越权", "rate_bps": 100},
    )
    assert response.status_code == 403


# --------------------------------------------------------------------------- #
# 账期：settlement hold period
# --------------------------------------------------------------------------- #


async def test_paid_but_uncompleted_order_stays_pending(
    client, admin_token, customer_token, db_session
):
    seller = await _seller(db_session)
    await _place_and_pay(client, customer_token, db_session)

    ledger = (
        await client.get(
            f"/api/v1/admin/sellers/{seller.id}/ledger", headers=bearer(admin_token)
        )
    ).json()["data"]
    assert ledger["balance_cents"] > 0
    assert ledger["available_cents"] == 0, "an order that is not completed cannot be withdrawn"
    assert ledger["pending_cents"] == ledger["balance_cents"]
    assert ledger["hold_days"] >= 0


async def test_completed_order_becomes_available_after_the_hold_period(
    client, admin_token, customer_token, db_session
):
    seller = await _seller(db_session)
    tenant = await db_session.get(Tenant, 1)
    tenant.settlement_hold_days = 7

    order = await _place_and_pay(client, customer_token, db_session)
    await _complete(db_session, order)

    # Just completed: still inside the 7-day hold window.
    ledger = (
        await client.get(
            f"/api/v1/admin/sellers/{seller.id}/ledger", headers=bearer(admin_token)
        )
    ).json()["data"]
    assert ledger["available_cents"] == 0
    assert ledger["pending_cents"] > 0

    # Move the completion far enough into the past to clear the hold period.
    seller_order = (
        await db_session.execute(select(SellerOrder).where(SellerOrder.order_id == order.id))
    ).scalars().first()
    seller_order.completed_at = datetime.now(UTC) - timedelta(days=8)
    await db_session.flush()

    cleared = (
        await client.get(
            f"/api/v1/admin/sellers/{seller.id}/ledger", headers=bearer(admin_token)
        )
    ).json()["data"]
    assert cleared["available_cents"] > 0
    assert cleared["pending_cents"] == 0


async def test_payout_is_blocked_inside_the_hold_period(
    client, admin_token, customer_token, db_session
):
    seller = await _seller(db_session)
    tenant = await db_session.get(Tenant, 1)
    tenant.settlement_hold_days = 30

    order = await _place_and_pay(client, customer_token, db_session)
    await _complete(db_session, order)

    response = await client.post(
        f"/api/v1/admin/sellers/{seller.id}/payouts", headers=bearer(admin_token)
    )
    assert response.status_code == 400
    assert "账期" in response.json()["message"]


# --------------------------------------------------------------------------- #
# 提现审核
# --------------------------------------------------------------------------- #


async def _withdrawable(client, admin_token, customer_token, db_session) -> tuple[int, int]:
    """Return (seller_id, payout_id) with a pending withdrawal request ready."""
    seller = await _seller(db_session)
    tenant = await db_session.get(Tenant, 1)
    tenant.settlement_hold_days = 0
    order = await _place_and_pay(client, customer_token, db_session)
    await _complete(db_session, order)

    payout = await client.post(
        f"/api/v1/admin/sellers/{seller.id}/payouts", headers=bearer(admin_token)
    )
    assert payout.status_code == 200, payout.text
    return seller.id, payout.json()["data"]["id"]


async def test_payout_request_starts_pending(client, admin_token, customer_token, db_session):
    _seller_id, payout_id = await _withdrawable(client, admin_token, customer_token, db_session)
    listed = await client.get(
        "/api/v1/admin/payouts", headers=bearer(admin_token), params={"status": "pending"}
    )
    assert listed.status_code == 200
    assert any(item["id"] == payout_id for item in listed.json()["data"])


async def test_rejected_payout_does_not_touch_the_ledger(
    client, admin_token, customer_token, db_session
):
    seller_id, payout_id = await _withdrawable(client, admin_token, customer_token, db_session)
    before = (
        await client.get(
            f"/api/v1/admin/sellers/{seller_id}/ledger", headers=bearer(admin_token)
        )
    ).json()["data"]["balance_cents"]

    rejected = await client.post(
        f"/api/v1/admin/payouts/{payout_id}/reject",
        headers=bearer(admin_token),
        json={"reason": "资料不全"},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["data"]["status"] == "rejected"
    assert rejected.json()["data"]["reject_reason"] == "资料不全"

    after = (
        await client.get(
            f"/api/v1/admin/sellers/{seller_id}/ledger", headers=bearer(admin_token)
        )
    ).json()["data"]["balance_cents"]
    assert after == before, "a rejected request must not move money"

    # A handled request cannot be approved afterwards.
    late = await client.post(
        f"/api/v1/admin/payouts/{payout_id}/approve", headers=bearer(admin_token)
    )
    assert late.status_code == 400


async def test_only_approved_payouts_can_be_paid(
    client, admin_token, customer_token, db_session
):
    _seller_id, payout_id = await _withdrawable(client, admin_token, customer_token, db_session)
    premature = await client.post(
        f"/api/v1/admin/payouts/{payout_id}/pay", headers=bearer(admin_token)
    )
    assert premature.status_code == 400

    await client.post(f"/api/v1/admin/payouts/{payout_id}/approve", headers=bearer(admin_token))
    paid = await client.post(
        f"/api/v1/admin/payouts/{payout_id}/pay", headers=bearer(admin_token)
    )
    assert paid.status_code == 200
    assert paid.json()["data"]["status"] == "paid"
    assert paid.json()["data"]["paid_at"]


async def test_second_payout_request_is_blocked_while_one_is_open(
    client, admin_token, customer_token, db_session
):
    seller_id, _payout_id = await _withdrawable(client, admin_token, customer_token, db_session)
    again = await client.post(
        f"/api/v1/admin/sellers/{seller_id}/payouts", headers=bearer(admin_token)
    )
    assert again.status_code == 409


# --------------------------------------------------------------------------- #
# 结算批次
# --------------------------------------------------------------------------- #


async def test_settlement_batch_lifecycle(
    client, admin_token, customer_token, db_session
):
    seller_id, payout_id = await _withdrawable(client, admin_token, customer_token, db_session)
    await client.post(f"/api/v1/admin/payouts/{payout_id}/approve", headers=bearer(admin_token))

    now = datetime.now(UTC)
    created = await client.post(
        "/api/v1/admin/settlement-batches",
        headers=bearer(admin_token),
        json={
            "period_start": (now - timedelta(days=1)).isoformat(),
            "period_end": (now + timedelta(days=1)).isoformat(),
            "note": "pytest 批次",
        },
    )
    assert created.status_code == 200, created.text
    batch = created.json()["data"]
    assert batch["status"] == "draft"
    assert batch["payout_count"] >= 1
    assert batch["total_amount_cents"] > 0

    # Draft batches cannot be paid directly.
    assert (
        await client.post(
            f"/api/v1/admin/settlement-batches/{batch['id']}/pay", headers=bearer(admin_token)
        )
    ).status_code == 400

    confirmed = await client.post(
        f"/api/v1/admin/settlement-batches/{batch['id']}/confirm", headers=bearer(admin_token)
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["data"]["status"] == "confirmed"

    paid = await client.post(
        f"/api/v1/admin/settlement-batches/{batch['id']}/pay", headers=bearer(admin_token)
    )
    assert paid.status_code == 200
    assert paid.json()["data"]["status"] == "paid"

    payouts = await client.get(
        "/api/v1/admin/payouts", headers=bearer(admin_token), params={"status": "paid"}
    )
    assert any(item["id"] == payout_id for item in payouts.json()["data"])

    ledger = (
        await client.get(
            f"/api/v1/admin/sellers/{seller_id}/ledger", headers=bearer(admin_token)
        )
    ).json()["data"]
    assert ledger["balance_cents"] == 0
    assert ledger["available_cents"] == 0


async def test_batch_requires_approved_payouts(client, admin_token):
    now = datetime.now(UTC)
    response = await client.post(
        "/api/v1/admin/settlement-batches",
        headers=bearer(admin_token),
        json={
            "period_start": (now - timedelta(days=1)).isoformat(),
            "period_end": (now + timedelta(days=1)).isoformat(),
        },
    )
    assert response.status_code == 400


async def test_batch_rejects_inverted_period(client, admin_token):
    now = datetime.now(UTC)
    response = await client.post(
        "/api/v1/admin/settlement-batches",
        headers=bearer(admin_token),
        json={
            "period_start": now.isoformat(),
            "period_end": (now - timedelta(days=1)).isoformat(),
        },
    )
    assert response.status_code == 400


async def test_settlement_batches_are_tenant_scoped(client, admin_token, platform_token):
    """A second tenant must not see the demo tenant's batches."""
    await client.post(
        "/api/v1/platform/tenants",
        headers=bearer(platform_token),
        json={
            "name": "Batch Other Tenant",
            "slug": "batch-other",
            "email": "batch-other@example.com",
            "nickname": "Other",
            "password": "Other@123456",
        },
    )
    other = (
        await client.post(
            "/api/v1/auth/login",
            json={"username": "batch-other@example.com", "password": "Other@123456"},
        )
    ).json()["data"]["access_token"]

    response = await client.get("/api/v1/admin/settlement-batches", headers=bearer(other))
    assert response.status_code == 200
    assert response.json()["data"] == []


async def test_commission_rule_rows_are_tenant_scoped(client, admin_token, db_session, platform_token):
    await client.post(
        "/api/v1/platform/tenants",
        headers=bearer(platform_token),
        json={
            "name": "Rule Other Tenant",
            "slug": "rule-other",
            "email": "rule-other@example.com",
            "nickname": "Other",
            "password": "Other@123456",
        },
    )
    other = (
        await client.post(
            "/api/v1/auth/login",
            json={"username": "rule-other@example.com", "password": "Other@123456"},
        )
    ).json()["data"]["access_token"]

    rules = await client.get("/api/v1/admin/commission-rules", headers=bearer(other))
    assert rules.status_code == 200
    demo_rules = (
        await db_session.execute(select(CommissionRule).where(CommissionRule.tenant_id == 1))
    ).scalars().all()
    returned_ids = {rule["id"] for rule in rules.json()["data"]}
    assert returned_ids.isdisjoint({rule.id for rule in demo_rules})


async def test_ledger_buckets_reconcile_after_a_payout(
    client, admin_token, customer_token, db_session
):
    """balance_cents must always equal available_cents + pending_cents."""
    seller_id, payout_id = await _withdrawable(client, admin_token, customer_token, db_session)
    await client.post(f"/api/v1/admin/payouts/{payout_id}/approve", headers=bearer(admin_token))
    await client.post(f"/api/v1/admin/payouts/{payout_id}/pay", headers=bearer(admin_token))

    # A second order that is still inside the hold window.
    tenant = await db_session.get(Tenant, 1)
    tenant.settlement_hold_days = 30
    await _place_and_pay(client, customer_token, db_session)

    ledger = (
        await client.get(
            f"/api/v1/admin/sellers/{seller_id}/ledger", headers=bearer(admin_token)
        )
    ).json()["data"]
    assert ledger["available_cents"] == 0
    assert ledger["pending_cents"] > 0
    assert ledger["balance_cents"] == ledger["available_cents"] + ledger["pending_cents"], (
        f"ledger does not reconcile: {ledger}"
    )
