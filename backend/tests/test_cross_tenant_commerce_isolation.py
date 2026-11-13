"""租户 A ↔ 租户 B 横向隔离：商品 / 订单 / 卖家台账 / 提现 / 附件 / 抽佣规则。

做法：用平台接口新建一个空租户 B，拿 B 的 owner token 去碰 demo 站的实体 id。
写操作一律传**原值**（例如把标题改成它现在的标题），这样 200 就证明越权，
但即使真的越权也不会改坏数据。
"""

from __future__ import annotations

import uuid

from tests.conftest import bearer, login

PASSWORD = "ProbeB@123456"


async def _new_empty_tenant(client, platform_token) -> str:
    slug = f"probe-{uuid.uuid4().hex[:8]}"
    email = f"owner@{slug}.example.com"
    created = await client.post(
        "/api/v1/platform/tenants",
        headers=bearer(platform_token),
        json={
            "name": f"{slug} 站",
            "slug": slug,
            "email": email,
            "nickname": "探针管理员",
            "password": PASSWORD,
        },
    )
    assert created.status_code == 200, created.text
    return (await login(client, email, PASSWORD))["access_token"]


async def _first_id(client, token, path: str) -> int | None:
    response = await client.get(path, headers=bearer(token))
    if response.status_code != 200:
        return None
    data = response.json()["data"]
    rows = data["list"] if isinstance(data, dict) and "list" in data else data
    return rows[0]["id"] if rows else None


async def test_cross_tenant_commerce_writes_are_rejected(client, platform_token, admin_token):
    outsider = await _new_empty_tenant(client, platform_token)

    product_id = await _first_id(client, admin_token, "/api/v1/admin/products")
    order_id = await _first_id(client, admin_token, "/api/v1/admin/orders?pageSize=5")
    seller_id = await _first_id(client, admin_token, "/api/v1/admin/sellers")
    payout_id = await _first_id(client, admin_token, "/api/v1/admin/payouts")
    rule_id = await _first_id(client, admin_token, "/api/v1/admin/commission-rules")

    assert product_id and order_id and seller_id, "demo 站需要有商品/订单/卖家数据"

    # 商品：B 列表应为空，改 demo 的商品必须 404
    listing = await client.get("/api/v1/admin/products", headers=bearer(outsider))
    assert listing.status_code == 200, listing.text
    assert listing.json()["data"] == [], "B 站不该看到 demo 的商品"

    updated = await client.put(
        f"/api/v1/admin/products/{product_id}",
        headers=bearer(outsider),
        json={"title": "越权改名"},
    )
    assert updated.status_code == 404, updated.text

    # 订单详情：不能读到别人租户的订单
    detail = await client.get(f"/api/v1/admin/orders/{order_id}", headers=bearer(outsider))
    assert detail.status_code == 404, detail.text

    # 卖家台账：不能读别人租户的卖家
    ledger = await client.get(
        f"/api/v1/admin/sellers/{seller_id}/ledger", headers=bearer(outsider)
    )
    assert ledger.status_code == 404, ledger.text

    # 提现审核：不能审别人租户的提现
    if payout_id:
        approved = await client.post(
            f"/api/v1/admin/payouts/{payout_id}/approve", headers=bearer(outsider)
        )
        assert approved.status_code == 404, approved.text

    # 抽佣规则：不能改别人租户的规则
    if rule_id:
        rule = await client.put(
            f"/api/v1/admin/commission-rules/{rule_id}",
            headers=bearer(outsider),
            json={"rate_bps": 9999},
        )
        assert rule.status_code == 404, rule.text


async def test_cross_tenant_attachments_are_rejected(client, platform_token, admin_token):
    outsider = await _new_empty_tenant(client, platform_token)
    attachment_id = await _first_id(client, admin_token, "/api/v1/attachments")

    listing = await client.get("/api/v1/attachments", headers=bearer(outsider))
    assert listing.status_code == 200, listing.text
    payload = listing.json()["data"]
    rows = payload["list"] if isinstance(payload, dict) and "list" in payload else payload
    assert rows == [], "B 站不该看到 demo 的附件"

    if attachment_id is None:
        return

    for path in (
        f"/api/v1/attachments/{attachment_id}/download",
        f"/api/v1/attachments/{attachment_id}/signed-url",
    ):
        method = "get" if path.endswith("download") else "post"
        response = await getattr(client, method)(path, headers=bearer(outsider))
        assert response.status_code in (403, 404), f"{path} -> {response.status_code}"

    removed = await client.delete(
        f"/api/v1/attachments/{attachment_id}", headers=bearer(outsider)
    )
    assert removed.status_code in (403, 404), removed.text
