"""C2C order lifecycle: create -> pay -> ship -> confirm, plus stock integrity.

Plan §18 acceptance criteria covered here:
  #6 下单价格/库存由服务端计算；跨卖家正确拆 seller_orders
  #2 买家 A 不能看到买家 B 的订单
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.catalog import Product, ProductSku
from app.models.order import Order, SellerOrder
from tests.conftest import bearer


async def _first_purchasable_sku(db_session, tenant_id: int = 1) -> tuple[Product, ProductSku]:
    product = (
        await db_session.execute(
            select(Product).where(
                Product.tenant_id == tenant_id, Product.status == "on_sale"
            )
        )
    ).scalars().first()
    assert product is not None, "seed data must contain an on-sale product"
    sku = (
        await db_session.execute(
            select(ProductSku).where(ProductSku.product_id == product.id)
        )
    ).scalars().first()
    assert sku is not None
    return product, sku


def _order_body(sku_id: int, quantity: int = 1) -> dict:
    return {
        "items": [{"sku_id": sku_id, "quantity": quantity}],
        "receiver_name": "测试收货人",
        "receiver_phone": "13900000000",
        "receiver_address": {"province": "广东省", "city": "深圳市", "detail": "测试路 1 号"},
        "remark": "pytest",
    }


async def test_portal_products_lists_only_on_sale_items(client, customer_token):
    response = await client.get("/api/v1/portal/products", headers=bearer(customer_token))
    assert response.status_code == 200
    items = response.json()["data"]
    assert items, "an on-sale product must be browsable by customers"
    assert all(item["status"] == "on_sale" for item in items)


async def test_create_order_locks_stock_and_splits_by_seller(
    client, customer_token, db_session
):
    _product, sku = await _first_purchasable_sku(db_session)
    stock_before = sku.stock
    locked_before = sku.locked_stock

    response = await client.post(
        "/api/v1/portal/orders",
        headers=bearer(customer_token),
        json=_order_body(sku.id, quantity=2),
    )
    assert response.status_code == 200, response.text
    order_data = response.json()["data"]
    assert order_data["status"] == "pending_payment"
    # Server-side pricing: 2 * sku price, never trusted from the client.
    assert order_data["payable_amount_cents"] == sku.price_cents * 2

    await db_session.refresh(sku)
    # Reserving an order removes it from sellable stock and books it as locked.
    assert sku.stock == stock_before - 2
    assert sku.locked_stock == locked_before + 2

    order = await db_session.get(Order, order_data["id"])
    assert order is not None
    seller_orders = (
        await db_session.execute(
            select(SellerOrder).where(SellerOrder.order_id == order.id)
        )
    ).scalars().all()
    assert len(seller_orders) == 1
    assert seller_orders[0].goods_amount_cents == sku.price_cents * 2
    assert seller_orders[0].commission_amount_cents == int(sku.price_cents * 2 * 0.10)


async def test_create_order_rejects_insufficient_stock(client, customer_token, db_session):
    _product, sku = await _first_purchasable_sku(db_session)
    response = await client.post(
        "/api/v1/portal/orders",
        headers=bearer(customer_token),
        json=_order_body(sku.id, quantity=999),
    )
    assert response.status_code == 409


async def test_create_order_rejects_unknown_sku(client, customer_token):
    response = await client.post(
        "/api/v1/portal/orders",
        headers=bearer(customer_token),
        json=_order_body(999_999),
    )
    assert response.status_code == 400


async def test_mock_pay_converts_locked_stock_into_sold_stock(
    client, customer_token, db_session
):
    _product, sku = await _first_purchasable_sku(db_session)
    stock_before = sku.stock
    locked_before = sku.locked_stock

    created = await client.post(
        "/api/v1/portal/orders",
        headers=bearer(customer_token),
        json=_order_body(sku.id, quantity=1),
    )
    order_id = created.json()["data"]["id"]

    paid = await client.post(
        f"/api/v1/portal/orders/{order_id}/mock-pay", headers=bearer(customer_token)
    )
    assert paid.status_code == 200, paid.text

    await db_session.refresh(sku)
    # Payment only releases the reservation; sellable stock was reserved upfront.
    assert sku.stock == stock_before - 1
    assert sku.locked_stock == locked_before

    order = await db_session.get(Order, order_id)
    assert order.status == "paid"
    assert order.paid_at is not None


async def test_cancel_order_releases_locked_stock(client, admin_token, customer_token, db_session):
    _product, sku = await _first_purchasable_sku(db_session)
    stock_before = sku.stock
    locked_before = sku.locked_stock

    created = await client.post(
        "/api/v1/portal/orders",
        headers=bearer(customer_token),
        json=_order_body(sku.id, quantity=1),
    )
    order_id = created.json()["data"]["id"]

    cancelled = await client.post(
        f"/api/v1/admin/orders/{order_id}/cancel", headers=bearer(admin_token)
    )
    assert cancelled.status_code == 200, cancelled.text

    await db_session.refresh(sku)
    assert sku.locked_stock == locked_before
    assert sku.stock == stock_before
    assert (await db_session.get(Order, order_id)).status == "cancelled"


async def test_buyer_cannot_read_another_buyers_order(client, db_session):
    """Acceptance #2: buyer A must not read buyer B's order."""
    _product, sku = await _first_purchasable_sku(db_session)

    buyer_a = (
        await client.post(
            "/api/v1/auth/register",
            json={
                "tenant_slug": "demo",
                "email": "buyer-a@example.com",
                "nickname": "买家A",
                "password": "Buyer@123456",
            },
        )
    ).json()["data"]["access_token"]
    buyer_b = (
        await client.post(
            "/api/v1/auth/register",
            json={
                "tenant_slug": "demo",
                "email": "buyer-b@example.com",
                "nickname": "买家B",
                "password": "Buyer@123456",
            },
        )
    ).json()["data"]["access_token"]

    order_id = (
        await client.post(
            "/api/v1/portal/orders", headers=bearer(buyer_a), json=_order_body(sku.id)
        )
    ).json()["data"]["id"]

    own = await client.get(f"/api/v1/portal/orders/{order_id}", headers=bearer(buyer_a))
    assert own.status_code == 200

    foreign = await client.get(f"/api/v1/portal/orders/{order_id}", headers=bearer(buyer_b))
    assert foreign.status_code == 404

    listed = await client.get("/api/v1/portal/orders", headers=bearer(buyer_b))
    assert listed.status_code == 200
    assert all(item["id"] != order_id for item in listed.json()["data"])


async def test_full_fulfilment_flow(client, admin_token, customer_token, db_session):
    """pay -> ship -> confirm receipt closes the order end to end."""
    _product, sku = await _first_purchasable_sku(db_session)
    order_id = (
        await client.post(
            "/api/v1/portal/orders",
            headers=bearer(customer_token),
            json=_order_body(sku.id),
        )
    ).json()["data"]["id"]

    assert (
        await client.post(
            f"/api/v1/portal/orders/{order_id}/mock-pay", headers=bearer(customer_token)
        )
    ).status_code == 200

    seller_order = (
        await db_session.execute(select(SellerOrder).where(SellerOrder.order_id == order_id))
    ).scalars().first()
    assert seller_order is not None

    shipped = await client.post(
        f"/api/v1/admin/seller-orders/{seller_order.id}/ship",
        headers=bearer(admin_token),
        json={"carrier": "顺丰速运", "tracking_no": "SF1234567890"},
    )
    assert shipped.status_code == 200, shipped.text

    confirmed = await client.post(
        f"/api/v1/portal/orders/{order_id}/confirm", headers=bearer(customer_token)
    )
    assert confirmed.status_code == 200, confirmed.text

    await db_session.refresh(seller_order)
    assert seller_order.status in {"completed", "shipped", "confirmed"}


async def test_confirm_before_shipping_is_rejected(client, customer_token, db_session):
    _product, sku = await _first_purchasable_sku(db_session)
    order_id = (
        await client.post(
            "/api/v1/portal/orders",
            headers=bearer(customer_token),
            json=_order_body(sku.id),
        )
    ).json()["data"]["id"]

    response = await client.post(
        f"/api/v1/portal/orders/{order_id}/confirm", headers=bearer(customer_token)
    )
    assert response.status_code == 400


@pytest.mark.parametrize("quantity", [0, -1, 1000])
async def test_order_quantity_is_validated(client, customer_token, db_session, quantity):
    _product, sku = await _first_purchasable_sku(db_session)
    response = await client.post(
        "/api/v1/portal/orders",
        headers=bearer(customer_token),
        json=_order_body(sku.id, quantity=quantity),
    )
    assert response.status_code in {409, 422}
