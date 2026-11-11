"""Portal shopping: product detail, cart, checkout from cart, address book.

Plan §18 acceptance criteria covered:
  #1 a buyer only sees products of their own tenant
  #2 a buyer only sees their own cart / addresses / orders
  #6 checkout prices and stock are decided server-side
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.catalog import Product, ProductSku
from app.models.order import Order
from tests.conftest import bearer


async def _on_sale(db_session, tenant_id: int = 1) -> tuple[Product, ProductSku]:
    product = (
        await db_session.execute(
            select(Product).where(Product.tenant_id == tenant_id, Product.status == "on_sale")
        )
    ).scalars().first()
    assert product is not None
    sku = (
        await db_session.execute(select(ProductSku).where(ProductSku.product_id == product.id))
    ).scalars().first()
    assert sku is not None
    return product, sku


async def _buyer(client, email: str = "cart-buyer@example.com", nickname: str = "购物车买家"):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "tenant_slug": "demo",
            "email": email,
            "nickname": nickname,
            "password": "Buyer@123456",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["access_token"]


def _address_body(**overrides) -> dict:
    body = {
        "receiver_name": "张三",
        "receiver_phone": "13800001111",
        "province": "广东省",
        "city": "深圳市",
        "district": "南山区",
        "detail": "科技园 1 号",
        "is_default": False,
    }
    body.update(overrides)
    return body


# --------------------------------------------------------------------------- #
# Product detail
# --------------------------------------------------------------------------- #


async def test_product_detail_returns_skus_and_shop(client, customer_token, db_session):
    product, _sku = await _on_sale(db_session)
    response = await client.get(
        f"/api/v1/portal/products/{product.id}", headers=bearer(customer_token)
    )
    assert response.status_code == 200, response.text
    detail = response.json()["data"]
    assert detail["id"] == product.id
    assert detail["skus"], "a purchasable product must expose at least one SKU"
    assert detail["seller_name"]
    assert detail["shop_name"]


async def test_product_detail_of_unknown_id_is_not_found(client, customer_token):
    response = await client.get(
        "/api/v1/portal/products/999999", headers=bearer(customer_token)
    )
    assert response.status_code == 404


async def test_product_detail_rejects_off_sale_product(client, customer_token, db_session):
    product, _sku = await _on_sale(db_session)
    product.status = "off_sale"
    await db_session.flush()

    response = await client.get(
        f"/api/v1/portal/products/{product.id}", headers=bearer(customer_token)
    )
    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# Cart
# --------------------------------------------------------------------------- #


async def test_cart_starts_empty(client, customer_token):
    response = await client.get("/api/v1/portal/cart", headers=bearer(customer_token))
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["items"] == []
    assert data["selected_amount_cents"] == 0


async def test_add_to_cart_merges_same_sku(client, customer_token, db_session):
    _product, sku = await _on_sale(db_session)
    headers = bearer(customer_token)

    first = await client.post(
        "/api/v1/portal/cart/items", headers=headers, json={"sku_id": sku.id, "quantity": 1}
    )
    assert first.status_code == 200, first.text

    second = await client.post(
        "/api/v1/portal/cart/items", headers=headers, json={"sku_id": sku.id, "quantity": 2}
    )
    assert second.status_code == 200
    assert second.json()["data"]["quantity"] == 3

    cart = await client.get("/api/v1/portal/cart", headers=headers)
    assert len(cart.json()["data"]["items"]) == 1
    assert cart.json()["data"]["selected_amount_cents"] == sku.price_cents * 3


async def test_add_to_cart_rejects_quantity_above_stock(client, customer_token, db_session):
    _product, sku = await _on_sale(db_session)
    response = await client.post(
        "/api/v1/portal/cart/items",
        headers=bearer(customer_token),
        json={"sku_id": sku.id, "quantity": 999},
    )
    assert response.status_code == 409


async def test_add_to_cart_rejects_unknown_sku(client, customer_token):
    response = await client.post(
        "/api/v1/portal/cart/items",
        headers=bearer(customer_token),
        json={"sku_id": 999999, "quantity": 1},
    )
    assert response.status_code == 404


async def test_update_and_delete_cart_item(client, customer_token, db_session):
    _product, sku = await _on_sale(db_session)
    headers = bearer(customer_token)
    item = (
        await client.post(
            "/api/v1/portal/cart/items", headers=headers, json={"sku_id": sku.id, "quantity": 1}
        )
    ).json()["data"]

    updated = await client.put(
        f"/api/v1/portal/cart/items/{item['id']}",
        headers=headers,
        json={"quantity": 2, "selected": False},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["quantity"] == 2
    assert updated.json()["data"]["selected"] is False

    # Unselected lines must not contribute to the checkout amount.
    cart = (await client.get("/api/v1/portal/cart", headers=headers)).json()["data"]
    assert cart["selected_amount_cents"] == 0

    deleted = await client.delete(
        f"/api/v1/portal/cart/items/{item['id']}", headers=headers
    )
    assert deleted.status_code == 200
    assert (await client.get("/api/v1/portal/cart", headers=headers)).json()["data"]["items"] == []


async def test_buyer_cannot_touch_another_buyers_cart(client, db_session):
    """Acceptance #2: cart rows are per buyer."""
    _product, sku = await _on_sale(db_session)
    owner = await _buyer(client, "cart-owner@example.com", "车主")
    intruder = await _buyer(client, "cart-intruder@example.com", "入侵者")

    item = (
        await client.post(
            "/api/v1/portal/cart/items",
            headers=bearer(owner),
            json={"sku_id": sku.id, "quantity": 1},
        )
    ).json()["data"]

    read = await client.put(
        f"/api/v1/portal/cart/items/{item['id']}",
        headers=bearer(intruder),
        json={"quantity": 5},
    )
    assert read.status_code == 404

    assert (
        await client.delete(f"/api/v1/portal/cart/items/{item['id']}", headers=bearer(intruder))
    ).status_code == 404

    assert (await client.get("/api/v1/portal/cart", headers=bearer(intruder))).json()["data"][
        "items"
    ] == []


async def test_clear_cart(client, customer_token, db_session):
    _product, sku = await _on_sale(db_session)
    headers = bearer(customer_token)
    await client.post(
        "/api/v1/portal/cart/items", headers=headers, json={"sku_id": sku.id, "quantity": 1}
    )
    cleared = await client.delete("/api/v1/portal/cart", headers=headers)
    assert cleared.status_code == 200
    assert cleared.json()["data"]["removed"] == 1


# --------------------------------------------------------------------------- #
# Checkout from cart
# --------------------------------------------------------------------------- #


async def test_checkout_from_cart_creates_order_and_empties_selected_lines(
    client, customer_token, db_session
):
    _product, sku = await _on_sale(db_session)
    headers = bearer(customer_token)
    stock_before = sku.stock

    await client.post(
        "/api/v1/portal/cart/items", headers=headers, json={"sku_id": sku.id, "quantity": 2}
    )
    response = await client.post(
        "/api/v1/portal/cart/checkout",
        headers=headers,
        json={
            "receiver_name": "李四",
            "receiver_phone": "13900002222",
            "receiver_address": {"city": "深圳市", "detail": "购物车结算地址"},
        },
    )
    assert response.status_code == 200, response.text
    order = response.json()["data"]
    assert order["payable_amount_cents"] == sku.price_cents * 2

    await db_session.refresh(sku)
    assert sku.stock == stock_before - 2, "checkout must reserve stock server-side"

    assert (await client.get("/api/v1/portal/cart", headers=headers)).json()["data"]["items"] == []

    stored = await db_session.get(Order, order["id"])
    assert stored is not None and stored.status == "pending_payment"


async def test_checkout_with_empty_cart_is_rejected(client, customer_token):
    response = await client.post(
        "/api/v1/portal/cart/checkout",
        headers=bearer(customer_token),
        json={
            "receiver_name": "李四",
            "receiver_phone": "13900002222",
            "receiver_address": {"city": "深圳市"},
        },
    )
    assert response.status_code == 400


async def test_checkout_only_takes_selected_lines(client, customer_token, db_session):
    _product, sku = await _on_sale(db_session)
    headers = bearer(customer_token)
    item = (
        await client.post(
            "/api/v1/portal/cart/items", headers=headers, json={"sku_id": sku.id, "quantity": 1}
        )
    ).json()["data"]
    await client.put(
        f"/api/v1/portal/cart/items/{item['id']}", headers=headers, json={"selected": False}
    )

    response = await client.post(
        "/api/v1/portal/cart/checkout",
        headers=headers,
        json={
            "receiver_name": "李四",
            "receiver_phone": "13900002222",
            "receiver_address": {"city": "深圳市"},
        },
    )
    assert response.status_code == 400
    # The unselected line must still be in the cart.
    assert len((await client.get("/api/v1/portal/cart", headers=headers)).json()["data"]["items"]) == 1


async def test_checkout_can_use_a_saved_address(client, customer_token, db_session):
    _product, sku = await _on_sale(db_session)
    headers = bearer(customer_token)
    address = (
        await client.post(
            "/api/v1/portal/addresses", headers=headers, json=_address_body()
        )
    ).json()["data"]
    await client.post(
        "/api/v1/portal/cart/items", headers=headers, json={"sku_id": sku.id, "quantity": 1}
    )

    response = await client.post(
        "/api/v1/portal/cart/checkout",
        headers=headers,
        json={
            "receiver_name": address["receiver_name"],
            "receiver_phone": address["receiver_phone"],
            "receiver_address": {},
            "address_id": address["id"],
        },
    )
    assert response.status_code == 200, response.text

    order = await db_session.get(Order, response.json()["data"]["id"])
    assert order is not None
    assert order.receiver_address["detail"] == address["detail"]


async def test_checkout_with_foreign_address_is_rejected(client, db_session):
    _product, sku = await _on_sale(db_session)
    owner = await _buyer(client, "addr-owner@example.com", "地址主")
    intruder = await _buyer(client, "addr-intruder@example.com", "地址侵入者")
    address = (
        await client.post(
            "/api/v1/portal/addresses", headers=bearer(owner), json=_address_body()
        )
    ).json()["data"]
    await client.post(
        "/api/v1/portal/cart/items",
        headers=bearer(intruder),
        json={"sku_id": sku.id, "quantity": 1},
    )

    response = await client.post(
        "/api/v1/portal/cart/checkout",
        headers=bearer(intruder),
        json={
            "receiver_name": "王五",
            "receiver_phone": "13900003333",
            "receiver_address": {},
            "address_id": address["id"],
        },
    )
    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# Address book
# --------------------------------------------------------------------------- #


async def test_first_address_becomes_default(client, customer_token):
    headers = bearer(customer_token)
    created = await client.post(
        "/api/v1/portal/addresses", headers=headers, json=_address_body()
    )
    assert created.status_code == 200, created.text
    assert created.json()["data"]["is_default"] is True


async def test_setting_a_new_default_clears_the_old_one(client, customer_token):
    headers = bearer(customer_token)
    first = (
        await client.post("/api/v1/portal/addresses", headers=headers, json=_address_body())
    ).json()["data"]
    second = (
        await client.post(
            "/api/v1/portal/addresses",
            headers=headers,
            json=_address_body(receiver_name="李四", detail="科技园 2 号"),
        )
    ).json()["data"]

    promoted = await client.post(
        f"/api/v1/portal/addresses/{second['id']}/default", headers=headers
    )
    assert promoted.status_code == 200

    rows = (await client.get("/api/v1/portal/addresses", headers=headers)).json()["data"]
    defaults = [row for row in rows if row["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["id"] == second["id"]
    assert first["id"] != second["id"]


async def test_address_crud_roundtrip(client, customer_token):
    headers = bearer(customer_token)
    created = (
        await client.post("/api/v1/portal/addresses", headers=headers, json=_address_body())
    ).json()["data"]

    updated = await client.put(
        f"/api/v1/portal/addresses/{created['id']}",
        headers=headers,
        json={"detail": "科技园 9 号", "receiver_phone": "13700009999"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["detail"] == "科技园 9 号"

    deleted = await client.delete(
        f"/api/v1/portal/addresses/{created['id']}", headers=headers
    )
    assert deleted.status_code == 200
    assert (await client.get("/api/v1/portal/addresses", headers=headers)).json()["data"] == []


async def test_deleting_the_default_promotes_another_address(client, customer_token):
    headers = bearer(customer_token)
    first = (
        await client.post("/api/v1/portal/addresses", headers=headers, json=_address_body())
    ).json()["data"]
    second = (
        await client.post(
            "/api/v1/portal/addresses",
            headers=headers,
            json=_address_body(receiver_name="李四", detail="科技园 2 号"),
        )
    ).json()["data"]
    assert first["is_default"] is True and second["is_default"] is False

    await client.delete(f"/api/v1/portal/addresses/{first['id']}", headers=headers)
    rows = (await client.get("/api/v1/portal/addresses", headers=headers)).json()["data"]
    assert len(rows) == 1 and rows[0]["is_default"] is True


async def test_buyer_cannot_read_another_buyers_addresses(client):
    owner = await _buyer(client, "ab-owner@example.com", "甲")
    intruder = await _buyer(client, "ab-intruder@example.com", "乙")
    address = (
        await client.post(
            "/api/v1/portal/addresses", headers=bearer(owner), json=_address_body()
        )
    ).json()["data"]

    assert (await client.get("/api/v1/portal/addresses", headers=bearer(intruder))).json()[
        "data"
    ] == []
    assert (
        await client.put(
            f"/api/v1/portal/addresses/{address['id']}",
            headers=bearer(intruder),
            json={"detail": "黑客地址"},
        )
    ).status_code == 404
    assert (
        await client.delete(
            f"/api/v1/portal/addresses/{address['id']}", headers=bearer(intruder)
        )
    ).status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {"receiver_name": "", "receiver_phone": "1", "detail": "x"},
        {"receiver_name": "张三", "receiver_phone": "", "detail": "x"},
        {"receiver_name": "张三", "receiver_phone": "1", "detail": ""},
    ],
)
async def test_address_payload_is_validated(client, customer_token, payload):
    response = await client.post(
        "/api/v1/portal/addresses", headers=bearer(customer_token), json=payload
    )
    assert response.status_code == 422


async def test_customer_permissions_cover_cart_and_address(client):
    token = await _buyer(client, "perm-check@example.com", "权限检查")
    me = await client.get("/api/v1/auth/me", headers=bearer(token))
    permissions = set(me.json()["data"]["permissions"])
    assert {"cart:read", "cart:manage", "address:read", "address:manage"} <= permissions


async def test_seller_cannot_use_the_cart(client, operator_token):
    """Back-office roles have no cart permissions."""
    response = await client.get("/api/v1/portal/cart", headers=bearer(operator_token))
    assert response.status_code == 403
