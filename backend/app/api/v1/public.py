"""公开接口：无需登录即可访问的只读数据。

租户身份来自请求 Host（B6）：tenant_domains 里 active 的域名 → 该租户。
Host 解析不出来时才走 ?tenant= 兜底，且兜底可用 settings.tenant_host_fallback 关掉 ——
线上必须是关的，否则未知域名会被静默当成 demo 站。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.response import ok
from app.services import public_catalog as public_catalog_service
from app.services import tenant_domains

router = APIRouter(prefix='/public', tags=['公开接口'])


async def _tenant_slug(
    request: Request, tenant: str | None, db: AsyncSession
) -> str:
    """Host 优先的租户解析；解析不到就是 404，不猜。"""
    record = await tenant_domains.resolve_public_tenant(db, request, tenant)
    return record.slug


@router.get('/products')
async def public_products(
    request: Request,
    tenant: str | None = Query(
        default=None,
        max_length=64,
        description='租户 slug（仅 Host 解析不出来时的兜底）',
    ),
    limit: int = Query(default=public_catalog_service.DEFAULT_LIMIT, ge=1, le=120),
    db: AsyncSession = Depends(get_db),
):
    """站点根页「商品」内页使用：匿名可读的在售商品橱窗。"""
    slug = await _tenant_slug(request, tenant, db)
    return ok(await public_catalog_service.list_public_products(db, slug, limit))


@router.get('/products/{product_id}')
async def public_product_detail(
    product_id: int,
    request: Request,
    tenant: str | None = Query(
        default=None,
        max_length=64,
        description='租户 slug（仅 Host 解析不出来时的兜底）',
    ),
    db: AsyncSession = Depends(get_db),
):
    """公开商品详情：匿名可浏览，含该商品的全部 SKU。"""
    slug = await _tenant_slug(request, tenant, db)
    return ok(await public_catalog_service.get_public_product(db, product_id, slug))


@router.get('/brand')
async def public_brand(
    request: Request,
    tenant: str | None = Query(
        default=None,
        max_length=64,
        description='租户 slug（仅 Host 解析不出来时的兜底）',
    ),
    db: AsyncSession = Depends(get_db),
):
    """站点品牌：匿名可读。登录页 / 站点标题 / 通知模板都要用。"""
    record = await tenant_domains.resolve_public_tenant(db, request, tenant)
    return ok(
        {
            'slug': record.slug,
            'name': record.name,
            'display_name': record.display_name or record.name,
            'logo_url': record.logo_url,
            'favicon_url': record.favicon_url,
            'theme_color': record.theme_color,
        }
    )
