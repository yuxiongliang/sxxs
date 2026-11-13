"""卖家中心与 IM 的横向隔离。

卖家中心的接口都不带 seller_id（卖家由 **当前登录用户 + 当前租户** 推导），
IM 会话则带 conversation_id。两条线都要保证：别的租户既读不到，也写不进。
"""

from __future__ import annotations

import uuid

from tests.conftest import bearer, login

PASSWORD = "ProbeS@123456"


async def _new_empty_tenant(client, platform_token) -> str:
    slug = f"probe-s-{uuid.uuid4().hex[:8]}"
    email = f"owner@{slug}.example.com"
    created = await client.post(
        "/api/v1/platform/tenants",
        headers=bearer(platform_token),
        json={
            "name": f"{slug} 站",
            "slug": slug,
            "email": email,
            "nickname": "卖家探针",
            "password": PASSWORD,
        },
    )
    assert created.status_code == 200, created.text
    return (await login(client, email, PASSWORD))["access_token"]


async def test_outsider_has_no_seller_center_data(client, platform_token):
    """新租户的 owner 在 demo 站不是卖家：卖家中心必须是空的或直接拒绝。"""
    outsider = await _new_empty_tenant(client, platform_token)

    for path in (
        "/api/v1/seller/profile",
        "/api/v1/seller/products",
        "/api/v1/seller/orders",
    ):
        response = await client.get(path, headers=bearer(outsider))
        assert response.status_code in (200, 400, 403, 404), f"{path} -> {response.status_code}"
        if response.status_code == 200:
            data = response.json()["data"]
            rows = data.get("list") if isinstance(data, dict) else data
            assert not rows, f"{path} 不该返回任何数据"

    # 不是卖家就不能给自己开商品
    created = await client.post(
        "/api/v1/seller/products",
        headers=bearer(outsider),
        json={"title": "越权商品", "price_cents": 100},
    )
    assert created.status_code in (400, 403, 404), created.text


async def test_im_conversation_is_tenant_private(client, platform_token, customer_token, db_session):
    from sqlalchemy import select

    from app.models.seller import Seller

    seller_id = await db_session.scalar(select(Seller.id).order_by(Seller.id).limit(1))
    assert seller_id is not None, "demo 站需要有卖家"

    # demo 的买家建一个会话
    conversation = await client.post(
        "/api/v1/im/conversations",
        headers=bearer(customer_token),
        json={"seller_id": seller_id},
    )
    assert conversation.status_code == 200, conversation.text
    conversation_id = conversation.json()["data"]["id"]

    outsider = await _new_empty_tenant(client, platform_token)

    # 1) 别的租户看不到这个会话（列表为空）
    listing = await client.get("/api/v1/im/conversations", headers=bearer(outsider))
    assert listing.status_code == 200, listing.text
    ids = {row["id"] for row in listing.json()["data"]}
    assert conversation_id not in ids, "别的租户不该看到 demo 的会话"

    # 2) 读消息、发消息都必须拒绝
    read = await client.get(
        f"/api/v1/im/conversations/{conversation_id}/messages", headers=bearer(outsider)
    )
    assert read.status_code in (403, 404), read.text

    written = await client.post(
        f"/api/v1/im/conversations/{conversation_id}/messages",
        headers=bearer(outsider),
        json={"content": "越权插话", "client_msg_id": "probe-im-1"},
    )
    assert written.status_code in (403, 404), written.text

    # 3) 也不能用别租户的 seller 开会话
    new_conv = await client.post(
        "/api/v1/im/conversations",
        headers=bearer(outsider),
        json={"seller_id": seller_id},
    )
    assert new_conv.status_code in (400, 403, 404), new_conv.text
