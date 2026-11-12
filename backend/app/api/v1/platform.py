from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_platform_permission
from app.core.response import ok
from app.schemas.platform import TenantCreate
from app.services import platform as platform_service

router = APIRouter(prefix="/platform", tags=["平台管理"])


@router.get("/tenants")
async def list_tenants(
    _context=Depends(require_platform_permission("platform:tenant:read")),
    db: AsyncSession = Depends(get_db),
):
    tenants = await platform_service.list_tenants(db)
    return ok(
        [
            {
                "id": item.id,
                "name": item.name,
                "slug": item.slug,
                "status": item.status,
                "created_at": item.created_at,
            }
            for item in tenants
        ]
    )


@router.post("/tenants")
async def create_tenant(
    payload: TenantCreate,
    _context=Depends(require_platform_permission("platform:tenant:manage")),
    db: AsyncSession = Depends(get_db),
):
    tenant = await platform_service.create_tenant(
        db, payload.name, payload.slug, payload.email, payload.nickname, payload.password
    )
    return ok(
        {"id": tenant.id, "name": tenant.name, "slug": tenant.slug, "status": tenant.status},
        "租户创建成功",
    )
