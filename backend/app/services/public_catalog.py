"""公开商品橱窗：站点根页「商品」内页用，无需登录。

字段白名单是硬约束 —— 这是对匿名访客开放的接口：

* 只返回商品展示信息（名称/副标题/主图/首个 SKU 的价格与库存）；
* 只返回 on_sale 商品、且卖家必须 active；
* 不暴露卖家状态、KYC、用户、订单、财务等内部字段；
* 租户不存在或非 active 一律 404，不泄露租户是否存在。

返回结构与前端 PortalProduct 保持一致，商品卡片可直接复用。
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Product, ProductSku
from app.models.seller import Seller, Shop
from app.models.tenant import Tenant

DEFAULT_TENANT_SLUG = "demo"
DEFAULT_LIMIT = 48
MAX_LIMIT = 120


async def resolve_tenant(db: AsyncSession, slug: str) -> Tenant:
    """公开的租户解析入口（品牌 / 商品列表都要用）。"""
    return await _resolve_tenant(db, slug)


async def _resolve_tenant(db: AsyncSession, slug: str) -> Tenant:
    """按 slug 解析租户；非 active 与不存在同样处理，避免被探测。"""
    tenant = (
        await db.scalars(select(Tenant).where(Tenant.slug == slug, Tenant.status == "active"))
    ).first()
    if tenant is None:
        raise HTTPException(status_code=404, detail="站点不存在或已停用")
    return tenant


def _product_public_dict(product, shop, seller, sku) -> dict:
    """列表与详情共用的一份字段白名单。"""
    return {
        "id": product.id,
        "seller_id": product.seller_id,
        "shop_id": product.shop_id,
        "name": product.name,
        "subtitle": product.subtitle,
        "status": product.status,
        "main_image": product.main_image,
        "shop_name": shop.name,
        "seller_name": seller.display_name,
        "sku": (
            {
                "id": sku.id,
                "name": sku.name,
                "price_cents": sku.price_cents,
                "stock": sku.stock,
            }
            if sku is not None
            else None
        ),
    }


async def list_public_products(
    db: AsyncSession, slug: str = DEFAULT_TENANT_SLUG, limit: int = DEFAULT_LIMIT
) -> list[dict]:
    """在售商品列表（公开）。价格/库存取该商品的第一个 SKU，与 Portal 展示一致。"""
    tenant = await _resolve_tenant(db, slug)
    bounded = max(1, min(limit, MAX_LIMIT))

    rows = (
        await db.execute(
            select(Product, Shop, Seller)
            .join(Shop, Shop.id == Product.shop_id)
            .join(Seller, Seller.id == Product.seller_id)
            .where(
                Product.tenant_id == tenant.id,
                Product.status == "on_sale",
                Seller.status == "active",
            )
            .order_by(Product.id.desc())
            .limit(bounded)
        )
    ).all()

    result: list[dict] = []
    for product, shop, seller in rows:
        sku = (
            await db.scalars(
                select(ProductSku).where(
                    ProductSku.tenant_id == tenant.id,
                    ProductSku.product_id == product.id,
                )
            )
        ).first()
        result.append(_product_public_dict(product, shop, seller, sku))
    return result


async def get_public_product(
    db: AsyncSession, product_id: int, slug: str = DEFAULT_TENANT_SLUG
) -> dict:
    """公开商品详情。非在售 / 卖家非 active / 跨租户一律 404，不区分原因。"""
    tenant = await _resolve_tenant(db, slug)
    row = (
        await db.execute(
            select(Product, Shop, Seller)
            .join(Shop, Shop.id == Product.shop_id)
            .join(Seller, Seller.id == Product.seller_id)
            .where(
                Product.tenant_id == tenant.id,
                Product.id == product_id,
                Product.status == "on_sale",
                Seller.status == "active",
            )
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="商品不存在或已下架")

    product, shop, seller = row
    skus = list(
        (
            await db.scalars(
                select(ProductSku)
                .where(
                    ProductSku.tenant_id == tenant.id,
                    ProductSku.product_id == product.id,
                )
                .order_by(ProductSku.id)
            )
        ).all()
    )
    payload = _product_public_dict(product, shop, seller, skus[0] if skus else None)
    payload["skus"] = [
        {
            "id": sku.id,
            "sku_code": sku.sku_code,
            "name": sku.name,
            "price_cents": sku.price_cents,
            "stock": sku.stock,
        }
        for sku in skus
    ]
    return payload
