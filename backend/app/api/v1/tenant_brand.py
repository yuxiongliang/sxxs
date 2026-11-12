"""租户自助维护站点品牌（全站名称 / logo / favicon / 主题色）。

为什么放在 tenants 表而不是 system_settings：
登录页、邮件模板、404 页在「配置还没加载」时就要用到品牌，
依赖 settings 会出现首屏空白。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_context, get_db, require_permission
from app.core.response import ok
from app.models.tenant import Tenant
from app.schemas.common import ApiResponse
from app.schemas.tenant_brand import TenantBrandOut, TenantBrandUpdate
from app.services.auth import AuthContext

router = APIRouter(prefix="/tenant/brand", tags=["租户品牌"])


def _serialize(record: Tenant) -> TenantBrandOut:
    return TenantBrandOut(
        tenant_id=record.id,
        slug=record.slug,
        name=record.name,
        display_name=record.display_name or record.name,
        logo_url=record.logo_url,
        favicon_url=record.favicon_url,
        theme_color=record.theme_color,
    )


@router.get("", response_model=ApiResponse[TenantBrandOut])
async def get_brand(
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    record = await db.get(Tenant, context.tenant.id)
    if record is None:
        raise HTTPException(status_code=404, detail="租户不存在")
    return ok(_serialize(record))


@router.put("", response_model=ApiResponse[TenantBrandOut])
async def save_brand(
    payload: TenantBrandUpdate,
    _context=Depends(require_permission("tenant:brand:manage")),
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    record = await db.get(Tenant, context.tenant.id)
    if record is None:
        raise HTTPException(status_code=404, detail="租户不存在")
    if payload.display_name is not None:
        record.display_name = payload.display_name or None
    if payload.logo_url is not None:
        record.logo_url = payload.logo_url or None
    if payload.favicon_url is not None:
        record.favicon_url = payload.favicon_url or None
    if payload.theme_color is not None:
        record.theme_color = payload.theme_color or None
    await db.commit()
    await db.refresh(record)
    return ok(_serialize(record), "品牌已保存")
