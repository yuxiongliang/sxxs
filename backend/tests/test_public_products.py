"""公开商品橱窗接口（站点根页「商品」内页用）。

这是项目里唯一对**匿名访客**开放的业务数据接口，因此断言集中在三件事：

1. 不带任何凭证也能读到；
2. 只返回 on_sale 商品，且不含卖家/用户等内部字段；
3. 不存在的租户与停用租户都返回 404（不泄露存在性）。
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.catalog import Product
from app.models.tenant import Tenant
from tests.conftest import bearer


async def test_anonymous_visitor_can_read_products(client):
    """不带 Authorization 头也要能拿到数据 —— 这是公开落地页的前提。"""
    response = await client.get("/api/v1/public/products")
    assert response.status_code == 200, response.text
    items = response.json()["data"]
    assert isinstance(items, list)
    assert items, "演示租户应当有在售商品"


async def test_only_on_sale_products_are_exposed(client, db_session):
    # 自己造一个「待审」商品，不依赖种子数据的分布
    existing = (
        (
            await db_session.execute(
                select(Product).where(Product.tenant_id == 1, Product.status == "on_sale")
            )
        )
        .scalars()
        .first()
    )
    assert existing is not None
    draft = Product(
        tenant_id=1,
        seller_id=existing.seller_id,
        shop_id=existing.shop_id,
        category_id=existing.category_id,
        name="待审商品（不应出现在公开橱窗）",
        status="pending_review",
    )
    db_session.add(draft)
    await db_session.flush()

    items = (await client.get("/api/v1/public/products?limit=120")).json()["data"]
    assert all(item["status"] == "on_sale" for item in items)
    assert draft.id not in {item["id"] for item in items}, "非在售商品被公开了"


async def test_response_is_whitelisted(client):
    """只暴露展示字段，不能带出卖家状态、KYC、用户等信息。"""
    item = (await client.get("/api/v1/public/products")).json()["data"][0]
    allowed = {
        "id",
        "seller_id",
        "shop_id",
        "name",
        "subtitle",
        "status",
        "main_image",
        "shop_name",
        "seller_name",
        "sku",
    }
    assert set(item) == allowed
    assert set(item["sku"] or {}) <= {"id", "name", "price_cents", "stock"}


async def test_unknown_tenant_returns_404(client):
    response = await client.get("/api/v1/public/products?tenant=no-such-market")
    assert response.status_code == 404


async def test_suspended_tenant_returns_404(client, db_session):
    tenant = await db_session.get(Tenant, 1)
    tenant.status = "suspended"
    await db_session.flush()
    response = await client.get("/api/v1/public/products?tenant=demo")
    assert response.status_code == 404


@pytest.mark.parametrize("query", ["limit=0", "limit=999"])
async def test_limit_is_bounded(client, query):
    response = await client.get(f"/api/v1/public/products?{query}")
    assert response.status_code == 422


async def test_limit_is_respected(client):
    items = (await client.get("/api/v1/public/products?limit=1")).json()["data"]
    assert len(items) <= 1


async def test_logged_in_user_sees_the_same_catalogue(client, customer_token):
    """公开接口与登录态无关，避免出现两套商品数据。"""
    anon = (await client.get("/api/v1/public/products")).json()["data"]
    authed = (await client.get("/api/v1/public/products", headers=bearer(customer_token))).json()[
        "data"
    ]
    assert [item["id"] for item in anon] == [item["id"] for item in authed]


async def test_anonymous_can_read_product_detail(client):
    """商品详情也要匿名可读 —— 站点前台的 /products/:id 依赖它。"""
    items = (await client.get("/api/v1/public/products?limit=1")).json()["data"]
    assert items, "需要至少一个在售商品"
    product_id = items[0]["id"]

    response = await client.get(f"/api/v1/public/products/{product_id}")
    assert response.status_code == 200, response.text
    detail = response.json()["data"]
    assert detail["id"] == product_id
    assert detail["status"] == "on_sale"
    assert isinstance(detail["skus"], list) and detail["skus"], "详情应带 SKU 列表"
    assert set(detail["skus"][0]) == {"id", "sku_code", "name", "price_cents", "stock"}


async def test_product_detail_hides_off_shelf_items(client, db_session):
    """下架商品对匿名访客必须 404，不能因为知道 id 就绕过。"""
    existing = (
        (
            await db_session.execute(
                select(Product).where(Product.tenant_id == 1, Product.status == "on_sale")
            )
        )
        .scalars()
        .first()
    )
    assert existing is not None
    draft = Product(
        tenant_id=1,
        seller_id=existing.seller_id,
        shop_id=existing.shop_id,
        category_id=existing.category_id,
        name="下架商品（详情不应可读）",
        status="off_sale",
    )
    db_session.add(draft)
    await db_session.flush()

    response = await client.get(f"/api/v1/public/products/{draft.id}")
    assert response.status_code == 404


async def test_unknown_product_detail_returns_404(client):
    response = await client.get("/api/v1/public/products/99999999")
    assert response.status_code == 404


async def test_product_detail_is_tenant_scoped(client, admin_token, platform_token):
    """别的租户拿不到 demo 的商品详情。"""
    await client.post(
        "/api/v1/platform/tenants",
        headers=bearer(platform_token),
        json={
            "name": "Detail Other Tenant",
            "slug": "detail-other",
            "email": "detail-other@example.com",
            "nickname": "Other",
            "password": "Other@123456",
        },
    )
    items = (await client.get("/api/v1/public/products?limit=1")).json()["data"]
    product_id = items[0]["id"]
    response = await client.get(f"/api/v1/public/products/{product_id}?tenant=detail-other")
    assert response.status_code == 404
