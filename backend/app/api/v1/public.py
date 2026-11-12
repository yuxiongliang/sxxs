"""公开接口：无需登录即可访问的只读数据。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.response import ok
from app.services import public_catalog as public_catalog_service

router = APIRouter(prefix="/public", tags=["公开接口"])


@router.get("/products")
async def public_products(
    tenant: str = Query(
        default=public_catalog_service.DEFAULT_TENANT_SLUG,
        max_length=64,
        description="租户 slug",
    ),
    limit: int = Query(default=public_catalog_service.DEFAULT_LIMIT, ge=1, le=120),
    db: AsyncSession = Depends(get_db),
):
    """站点根页「商品」内页使用：匿名可读的在售商品橱窗。"""
    return ok(await public_catalog_service.list_public_products(db, tenant, limit))


@router.get("/products/{product_id}")
async def public_product_detail(
    product_id: int,
    tenant: str = Query(
        default=public_catalog_service.DEFAULT_TENANT_SLUG,
        max_length=64,
        description="租户 slug",
    ),
    db: AsyncSession = Depends(get_db),
):
    """公开商品详情：匿名可浏览，含该商品的全部 SKU。"""
    return ok(await public_catalog_service.get_public_product(db, product_id, tenant))


@router.get("/brand")
async def public_brand(
    tenant: str = Query(
        default=public_catalog_service.DEFAULT_TENANT_SLUG,
        max_length=64,
        description="租户 slug",
    ),
    db: AsyncSession = Depends(get_db),
):
    """站点品牌：匿名可读。登录页 / 站点标题 / 通知模板都要用。"""
    record = await public_catalog_service.resolve_tenant(db, tenant)
    return ok(
        {
            "slug": record.slug,
            "name": record.name,
            "display_name": record.display_name or record.name,
            "logo_url": record.logo_url,
            "favicon_url": record.favicon_url,
            "theme_color": record.theme_color,
        }
    )
