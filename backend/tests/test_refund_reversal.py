"""退款冲正：a refund must reverse BOTH the goods and the commission in the ledger.

Before this module existed, `refund_seller_order` only flipped statuses: the
seller's `sale` / `commission` ledger entries stayed untouched, so refunded
money sat in the ledger forever and the platform never gave the commission back.

Plan §18 acceptance criterion #8: commission / refund / settlement / payout
balances must stay reconcilable.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from app.models.catalog import Product, ProductSku
from app.models.order import SellerOrder
from app.models.seller import Seller
from tests.conftest import bearer


async def _seller(db_session, tenant_id: int = 1) -> Seller:
    seller = (
        (
            await db_session.execute(
                select(Seller).where(Seller.tenant_id == tenant_id, Seller.status == "active")
            )
        )
        .scalars()
        .first()
    )
    assert seller is not None
    return seller


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


async def _place_and_pay(client, customer_token, db_session, quantity: int = 1) -> SellerOrder:
    """Place a portal order, pay it and return its single seller_order."""
    sku = await _sku(db_session)
    order_id = (
        await client.post(
            "/api/v1/portal/orders",
            headers=bearer(customer_token),
            json={
                "items": [{"sku_id": sku.id, "quantity": quantity}],
                "receiver_name": "退款测试",
                "receiver_phone": "13900002222",
                "receiver_address": {"city": "深圳市", "detail": "测试路 2 号"},
            },
        )
    ).json()["data"]["id"]
    await client.post(f"/api/v1/portal/orders/{order_id}/mock-pay", headers=bearer(customer_token))
    seller_order = (
        (await db_session.execute(select(SellerOrder).where(SellerOrder.order_id == order_id)))
        .scalars()
        .first()
    )
    assert seller_order is not None
    return seller_order


async def _ledger(client, admin_token, seller_id: int) -> dict:
    response = await client.get(
        f"/api/v1/admin/sellers/{seller_id}/ledger", headers=bearer(admin_token)
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def _refund(
    client, admin_token, seller_order_id: int, amount_cents: int, reason: str = "测试退款"
):
    return await client.post(
        f"/api/v1/admin/seller-orders/{seller_order_id}/refund",
        headers=bearer(admin_token),
        json={"amount_cents": amount_cents, "reason": reason},
    )


def _entries(ledger: dict, seller_order_id: int, entry_type: str) -> list[dict]:
    return [
        item
        for item in ledger["entries"]
        if item["seller_order_id"] == seller_order_id and item["type"] == entry_type
    ]


async def test_full_refund_reverses_goods_and_commission(
    client, admin_token, customer_token, db_session
):
    seller = await _seller(db_session)
    seller_order = await _place_and_pay(client, customer_token, db_session)
    goods = seller_order.goods_amount_cents
    commission = seller_order.commission_amount_cents
    assert commission > 0, "the demo commission rule must charge something"

    before = await _ledger(client, admin_token, seller.id)
    assert before["balance_cents"] == goods - commission

    response = await _refund(client, admin_token, seller_order.id, goods)
    assert response.status_code == 200, response.text

    after = await _ledger(client, admin_token, seller.id)
    refunds = _entries(after, seller_order.id, "refund")
    commission_reversals = _entries(after, seller_order.id, "refund_commission")
    assert len(refunds) == 1, f"expected exactly one goods reversal, got {refunds}"
    assert refunds[0]["amount_cents"] == -goods
    assert len(commission_reversals) == 1, (
        f"a refund must give the commission back, got {commission_reversals}"
    )
    assert commission_reversals[0]["amount_cents"] == commission

    assert after["balance_cents"] == 0, "a fully refunded order must not leave money behind"
    assert after["available_cents"] == 0
    assert after["pending_cents"] == 0

    logs = await client.get(
        "/api/v1/audit-logs",
        headers=bearer(admin_token),
        params={
            "pageSize": 100,
            "action": "seller_order.refunded",
            "target_id": seller_order.id,
        },
    )
    rows = logs.json()["data"]["list"]
    assert rows, "the refund must stay auditable"
    assert rows[0]["after"]["commission_reversed_cents"] == commission, (
        "the audit trail must show how much commission the platform clawed back"
    )


async def test_partial_refund_reverses_commission_proportionally(
    client, admin_token, customer_token, db_session
):
    seller = await _seller(db_session)
    seller_order = await _place_and_pay(client, customer_token, db_session, quantity=2)
    goods = seller_order.goods_amount_cents
    commission = seller_order.commission_amount_cents
    half = goods // 2

    response = await _refund(client, admin_token, seller_order.id, half, reason="部分退款")
    assert response.status_code == 200, response.text

    after = await _ledger(client, admin_token, seller.id)
    reversals = _entries(after, seller_order.id, "refund_commission")
    assert len(reversals) == 1
    assert reversals[0]["amount_cents"] == commission * half // goods
    assert after["balance_cents"] == goods - commission - half + reversals[0]["amount_cents"]


async def test_second_refund_is_rejected_and_does_not_double_reverse(
    client, admin_token, customer_token, db_session
):
    seller = await _seller(db_session)
    seller_order = await _place_and_pay(client, customer_token, db_session)
    goods = seller_order.goods_amount_cents

    assert (await _refund(client, admin_token, seller_order.id, goods)).status_code == 200
    again = await _refund(client, admin_token, seller_order.id, goods)
    assert again.status_code == 400

    ledger = await _ledger(client, admin_token, seller.id)
    assert len(_entries(ledger, seller_order.id, "refund")) == 1
    assert len(_entries(ledger, seller_order.id, "refund_commission")) == 1
    assert ledger["balance_cents"] == 0


async def test_refund_of_an_unpaid_order_writes_no_reversal_entries(
    client, admin_token, customer_token, db_session
):
    """Nothing was ever credited, so reversing would invent a negative balance."""
    seller = await _seller(db_session)
    sku = await _sku(db_session)
    order_id = (
        await client.post(
            "/api/v1/portal/orders",
            headers=bearer(customer_token),
            json={
                "items": [{"sku_id": sku.id, "quantity": 1}],
                "receiver_name": "未支付退款",
                "receiver_phone": "13900003333",
                "receiver_address": {"city": "深圳市", "detail": "测试路 3 号"},
            },
        )
    ).json()["data"]["id"]
    seller_order = (
        (await db_session.execute(select(SellerOrder).where(SellerOrder.order_id == order_id)))
        .scalars()
        .first()
    )
    assert seller_order is not None
    assert seller_order.status == "pending_payment"

    response = await _refund(client, admin_token, seller_order.id, seller_order.goods_amount_cents)
    assert response.status_code == 200, response.text

    ledger = await _ledger(client, admin_token, seller.id)
    assert _entries(ledger, seller_order.id, "refund") == []
    assert _entries(ledger, seller_order.id, "refund_commission") == []
    assert ledger["balance_cents"] == 0


async def test_ledger_still_reconciles_after_a_refund(
    client, admin_token, customer_token, db_session
):
    seller = await _seller(db_session)
    refunded = await _place_and_pay(client, customer_token, db_session)
    assert (
        await _refund(client, admin_token, refunded.id, refunded.goods_amount_cents)
    ).status_code == 200
    # A second, untouched order keeps a non-zero balance around.
    await _place_and_pay(client, customer_token, db_session)

    ledger = await _ledger(client, admin_token, seller.id)
    assert ledger["balance_cents"] == ledger["available_cents"] + ledger["pending_cents"], (
        f"ledger does not reconcile after a refund: {ledger}"
    )


async def test_refund_after_completion_keeps_the_ledger_reconcilable(
    client, admin_token, customer_token, db_session
):
    """A completed order that gets refunded must net out to zero, not to a frozen pending bucket."""
    seller = await _seller(db_session)
    seller_order = await _place_and_pay(client, customer_token, db_session)
    seller_order.status = "completed"
    seller_order.completed_at = datetime.now(UTC)
    await db_session.flush()

    assert (
        await _refund(client, admin_token, seller_order.id, seller_order.goods_amount_cents)
    ).status_code == 200

    ledger = await _ledger(client, admin_token, seller.id)
    assert ledger["balance_cents"] == 0
    assert ledger["available_cents"] == 0
    assert ledger["pending_cents"] == 0
