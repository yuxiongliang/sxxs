"""买家 -> 店主：自助申请开店，并在同一套买家入口里管理自己的店。

覆盖点：

1. 注册即买家；买家可自助申请开店，申请后是 pending。
2. 重复申请 409（不会插出第二个卖家/店铺）。
3. **卖家中心接口按归属权鉴权**：买家角色本身没有 seller:manage 权限码，
   审核通过后仍然必须能管理自己的商品/订单/结算 —— 这是本次重构的核心。
4. 管理员审核通过后才真正可用（pending 时 profile 返回 403）。
"""

from __future__ import annotations

from tests.conftest import bearer


async def _apply(client, token, shop_name="我的小店"):
    return await client.post(
        "/api/v1/portal/seller/apply",
        headers=bearer(token),
        json={"shop_name": shop_name, "contact_phone": "13900001234"},
    )


async def test_buyer_starts_without_a_shop(client, customer_token):
    response = await client.get("/api/v1/portal/seller/application", headers=bearer(customer_token))
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["has_seller"] is False
    assert data["status"] == "none"


async def test_buyer_can_apply_and_becomes_pending(client, customer_token):
    created = await _apply(client, customer_token, "阿强的二手键盘铺")
    assert created.status_code == 200, created.text
    data = created.json()["data"]
    assert data["status"] == "pending"
    assert data["shop"]["name"] == "阿强的二手键盘铺"

    again = await client.get("/api/v1/portal/seller/application", headers=bearer(customer_token))
    assert again.json()["data"]["has_seller"] is True
    assert again.json()["data"]["status"] == "pending"


async def test_duplicate_application_is_rejected(client, customer_token):
    assert (await _apply(client, customer_token)).status_code == 200
    second = await _apply(client, customer_token, "第二个店")
    assert second.status_code == 409
    assert "无需重复申请" in second.json()["message"]


async def test_shop_name_is_validated(client, customer_token):
    bad = await _apply(client, customer_token, "x")
    assert bad.status_code == 422


async def test_pending_seller_cannot_open_the_shop_yet(client, customer_token):
    assert (await _apply(client, customer_token)).status_code == 200
    profile = await client.get("/api/v1/portal/seller/profile", headers=bearer(customer_token))
    assert profile.status_code == 403, "审核通过前不能进卖家中心"


async def test_approved_seller_manages_shop_without_staff_permissions(
    client, admin_token, customer_token
):
    """买家角色没有 seller:manage 权限码，但审核通过后必须能管理自己的店。"""
    applied = await _apply(client, customer_token, "阿强的二手键盘铺")
    seller_id = applied.json()["data"]["seller_id"]

    approved = await client.post(
        f"/api/v1/admin/sellers/{seller_id}/review",
        headers=bearer(admin_token),
        json={"status": "active", "kyc_status": "approved"},
    )
    assert approved.status_code == 200, approved.text

    profile = await client.get("/api/v1/portal/seller/profile", headers=bearer(customer_token))
    assert profile.status_code == 200, profile.text
    assert profile.json()["data"]["status"] == "active"

    created = await client.post(
        "/api/v1/portal/seller/products",
        headers=bearer(customer_token),
        json={
            "name": "自营键盘",
            "price_cents": 12900,
            "stock": 3,
            "description": "开店主上架的第一个商品",
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["data"]["status"] == "pending_review"

    listed = await client.get("/api/v1/portal/seller/products", headers=bearer(customer_token))
    assert listed.status_code == 200, listed.text
    assert any(item["name"] == "自营键盘" for item in listed.json()["data"])


async def test_application_only_affects_the_applicant(client, customer):
    """另一个买家看不到、也无法使用别人的店。"""
    assert (await _apply(client, customer["access_token"])).status_code == 200

    second = await client.post(
        "/api/v1/auth/register",
        json={
            "tenant_slug": "demo",
            "email": "buyer-two-apply@example.com",
            "nickname": "买家二号",
            "password": "Buyer@123456",
        },
    )
    token2 = second.json()["data"]["access_token"]
    status2 = await client.get("/api/v1/portal/seller/application", headers=bearer(token2))
    assert status2.json()["data"]["has_seller"] is False
    assert (await _apply(client, token2, "二号店")).status_code == 200
