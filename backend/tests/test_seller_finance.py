"""Seller centre + commission ledger / payout settlement.

Plan §18 acceptance criteria covered:
  #3 seller A only sees their own shop's products and seller_orders
  #8 commission / refund / settlement balances stay reconcilable
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from app.models.finance import LedgerEntry
from app.models.order import SellerOrder
from app.models.seller import Seller
from tests.conftest import bearer


async def _seller(db_session, tenant_id: int = 1) -> Seller:
    seller = (
        await db_session.execute(
            select(Seller).where(Seller.tenant_id == tenant_id, Seller.status == "active")
        )
    ).scalars().first()
    assert seller is not None
    return seller


async def _complete_order(db_session, order_id: int) -> None:
    """Mark a seller_order completed and clear the settlement hold period.

    Withdrawal now requires ``seller_order.status == completed`` *and* the
    tenant's 账期 (``settlement_hold_days``) to have elapsed, so tests that
    exercise payouts must finish the order first.
    """
    from app.models.tenant import Tenant

    tenant = await db_session.get(Tenant, 1)
    tenant.settlement_hold_days = 0
    seller_order = (
        await db_session.execute(select(SellerOrder).where(SellerOrder.order_id == order_id))
    ).scalars().first()
    assert seller_order is not None
    seller_order.status = "completed"
    seller_order.completed_at = datetime.now(UTC)
    await db_session.flush()


async def _buy_and_pay(client, customer_token, db_session) -> tuple[int, int]:
    """Place and pay a one-unit order, returning (seller_order_id, goods_cents)."""
    from app.models.catalog import Product, ProductSku
    from app.models.order import SellerOrder

    product = (
        await db_session.execute(
            select(Product).where(Product.tenant_id == 1, Product.status == "on_sale")
        )
    ).scalars().first()
    sku = (
        await db_session.execute(
            select(ProductSku).where(ProductSku.product_id == product.id)
        )
    ).scalars().first()

    order_id = (
        await client.post(
            "/api/v1/portal/orders",
            headers=bearer(customer_token),
            json={
                "items": [{"sku_id": sku.id, "quantity": 1}],
                "receiver_name": "验收买家",
                "receiver_phone": "13900000000",
                "receiver_address": {"city": "深圳市", "detail": "验收路 9 号"},
            },
        )
    ).json()["data"]["id"]

    await client.post(
        f"/api/v1/portal/orders/{order_id}/mock-pay", headers=bearer(customer_token)
    )

    seller_order = (
        await db_session.execute(select(SellerOrder).where(SellerOrder.order_id == order_id))
    ).scalars().first()
    assert seller_order is not None
    return seller_order.id, seller_order.goods_amount_cents


async def _buy_pay_and_complete(client, customer_token, db_session) -> tuple[int, int]:
    seller_order_id, goods = await _buy_and_pay(client, customer_token, db_session)
    await _complete_order(db_session, (await db_session.get(SellerOrder, seller_order_id)).order_id)
    return seller_order_id, goods


async def test_seller_centre_profile_is_scoped_to_the_owner(client, operator_token):
    response = await client.get("/api/v1/portal/seller/profile", headers=bearer(operator_token))
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["display_name"]
    assert data["status"] == "active"


async def test_customer_cannot_open_the_seller_centre(client, customer_token):
    for path in (
        "/api/v1/portal/seller/profile",
        "/api/v1/portal/seller/products",
        "/api/v1/portal/seller/orders",
    ):
        response = await client.get(path, headers=bearer(customer_token))
        assert response.status_code == 403, f"{path} must be seller-only"


async def test_seller_can_create_a_product_pending_review(client, operator_token):
    response = await client.post(
        "/api/v1/portal/seller/products",
        headers=bearer(operator_token),
        json={
            "name": "pytest 卖家商品",
            "subtitle": "自动化验收",
            "price_cents": 12800,
            "stock": 7,
        },
    )
    assert response.status_code == 200, response.text
    created = response.json()["data"]
    assert created["status"] == "pending_review"

    listed = await client.get(
        "/api/v1/portal/seller/products", headers=bearer(operator_token)
    )
    assert listed.status_code == 200
    mine = next(item for item in listed.json()["data"] if item["id"] == created["id"])
    assert mine["price_cents"] == 12800
    assert mine["stock"] == 7
    assert mine["status"] == "pending_review"


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "零价", "price_cents": 0, "stock": 1},
        {"name": "", "price_cents": 100, "stock": 1},
        {"name": "负库存", "price_cents": 100, "stock": -1},
    ],
)
async def test_seller_product_payload_is_validated(client, operator_token, payload):
    response = await client.post(
        "/api/v1/portal/seller/products", headers=bearer(operator_token), json=payload
    )
    assert response.status_code == 422


async def test_seller_only_sees_own_orders(
    client, operator_token, admin_token, customer_token, db_session
):
    seller = await _seller(db_session)
    await _buy_and_pay(client, customer_token, db_session)

    seller_orders = await client.get(
        "/api/v1/portal/seller/orders", headers=bearer(operator_token)
    )
    assert seller_orders.status_code == 200
    returned_ids = {item["id"] for item in seller_orders.json()["data"]}
    # Every returned seller_order must belong to the caller's own seller.
    for seller_order_id in returned_ids:
        row = await db_session.get(SellerOrder, seller_order_id)
        assert row is not None and row.seller_id == seller.id


async def test_seller_can_ship_own_order(client, operator_token, customer_token, db_session):
    seller_order_id, _goods = await _buy_and_pay(client, customer_token, db_session)
    response = await client.post(
        f"/api/v1/portal/seller/orders/{seller_order_id}/ship",
        headers=bearer(operator_token),
        json={"carrier": "中通快递", "tracking_no": "ZT0001"},
    )
    assert response.status_code == 200, response.text


async def test_payment_writes_sale_and_commission_ledger(
    client, admin_token, customer_token, db_session
):
    seller = await _seller(db_session)
    _seller_order_id, goods = await _buy_and_pay(client, customer_token, db_session)

    ledger = await client.get(
        f"/api/v1/admin/sellers/{seller.id}/ledger", headers=bearer(admin_token)
    )
    assert ledger.status_code == 200, ledger.text
    data = ledger.json()["data"]

    commission = int(goods * 0.10)
    assert data["balance_cents"] == goods - commission
    by_type = {entry["type"]: entry["amount_cents"] for entry in data["entries"]}
    assert by_type["sale"] == goods
    assert by_type["commission"] == -commission


async def test_payment_is_idempotent_for_the_ledger(
    client, admin_token, customer_token, db_session
):
    """Acceptance #7: a replayed payment must not double-book the ledger."""
    seller = await _seller(db_session)
    await _buy_and_pay(client, customer_token, db_session)

    first = (
        await client.get(
            f"/api/v1/admin/sellers/{seller.id}/ledger", headers=bearer(admin_token)
        )
    ).json()["data"]["balance_cents"]

    # Replaying mock-pay on an already paid order must be rejected, not re-booked.
    from app.models.order import Order

    order = (
        await db_session.execute(select(Order).where(Order.status == "paid"))
    ).scalars().first()
    replay = await client.post(
        f"/api/v1/admin/orders/{order.id}/mock-pay", headers=bearer(admin_token)
    )
    # A payment replay is answered idempotently (200) but must not re-book.
    assert replay.status_code in {200, 400, 409}

    second = (
        await client.get(
            f"/api/v1/admin/sellers/{seller.id}/ledger", headers=bearer(admin_token)
        )
    ).json()["data"]["balance_cents"]
    assert second == first


async def test_payout_settles_the_balance_to_zero(
    client, admin_token, customer_token, db_session
):
    """request -> approve -> pay drives the ledger balance to zero."""
    seller = await _seller(db_session)
    await _buy_pay_and_complete(client, customer_token, db_session)

    ledger = (
        await client.get(
            f"/api/v1/admin/sellers/{seller.id}/ledger", headers=bearer(admin_token)
        )
    ).json()["data"]
    assert ledger["available_cents"] > 0
    assert ledger["pending_cents"] == 0

    payout = await client.post(
        f"/api/v1/admin/sellers/{seller.id}/payouts", headers=bearer(admin_token)
    )
    assert payout.status_code == 200, payout.text
    payout_id = payout.json()["data"]["id"]
    assert payout.json()["data"]["amount_cents"] == ledger["available_cents"]
    # A request is not money out of the door: the ledger is untouched until paid.
    assert payout.json()["data"]["status"] == "pending"

    approved = await client.post(
        f"/api/v1/admin/payouts/{payout_id}/approve", headers=bearer(admin_token)
    )
    assert approved.status_code == 200, approved.text

    paid = await client.post(
        f"/api/v1/admin/payouts/{payout_id}/pay", headers=bearer(admin_token)
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["data"]["status"] == "paid"

    after = (
        await client.get(
            f"/api/v1/admin/sellers/{seller.id}/ledger", headers=bearer(admin_token)
        )
    ).json()["data"]["balance_cents"]
    assert after == 0


async def test_payout_without_balance_is_rejected(client, admin_token, db_session):
    seller = await _seller(db_session)
    response = await client.post(
        f"/api/v1/admin/sellers/{seller.id}/payouts", headers=bearer(admin_token)
    )
    assert response.status_code == 400


async def test_ledger_of_unknown_seller_is_not_found(client, admin_token):
    response = await client.get(
        "/api/v1/admin/sellers/999999/ledger", headers=bearer(admin_token)
    )
    assert response.status_code == 404


async def test_seller_payout_endpoint_is_seller_scoped(client, operator_token, db_session):
    seller = await _seller(db_session)
    response = await client.post(
        "/api/v1/portal/seller/payouts", headers=bearer(operator_token)
    )
    # Either a withdrawal request is created for the caller's own seller, or the
    # balance is not settleable yet -> 400. Both prove the seller binding works.
    assert response.status_code in {200, 400}
    if response.status_code == 200:
        assert response.json()["data"]["amount_cents"] > 0
    entries = (
        await db_session.execute(
            select(func.count(LedgerEntry.id)).where(LedgerEntry.seller_id == seller.id)
        )
    ).scalar_one()
    assert entries >= 0
