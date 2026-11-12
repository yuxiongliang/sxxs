"""平台级业务类目与租户归类。

类目决定「平台向这家租户抽多少佣」（commission_bps 万分比）；
买断套餐的租户按 0 处理，是套餐侧的性质，不写回类目。

读要 platform:tenant:read，写要 platform:tenant:manage。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_platform_permission
from app.core.response import ok
from app.schemas.common import ApiResponse
from app.schemas.platform import (
    ServiceCategoryCreate,
    ServiceCategoryUpdate,
    TenantCategoryAssign,
)
from app.services import commission as commission_service
from app.services import service_category as category_service

router = APIRouter(prefix="/platform", tags=["平台业务类目"])


@router.get("/commission-report", response_model=ApiResponse[dict])
async def commission_report(
    month: str | None = Query(default=None, description="YYYY-MM，默认当月"),
    _context=Depends(require_platform_permission("platform:tenant:read")),
    db: AsyncSession = Depends(get_db),
):
    """按月抽佣台账（只读）：GMV × 类目比例；买断/自定义档期租户恒为 0。"""
    return ok(await commission_service.monthly_report(db, month))


@router.get("/service-categories", response_model=ApiResponse[list[dict]])
async def list_service_categories(
    include_archived: bool = Query(default=False),
    _context=Depends(require_platform_permission("platform:tenant:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await category_service.list_categories(db, include_archived))


@router.post("/service-categories", response_model=ApiResponse[dict])
async def create_service_category(
    payload: ServiceCategoryCreate,
    _context=Depends(require_platform_permission("platform:tenant:manage")),
    db: AsyncSession = Depends(get_db),
):
    category = await category_service.create_category(
        db,
        code=payload.code,
        name=payload.name,
        description=payload.description,
        commission_bps=payload.commission_bps,
        sort=payload.sort,
    )
    await db.commit()
    await db.refresh(category)
    return ok(
        {
            "id": category.id,
            "code": category.code,
            "name": category.name,
            "description": category.description,
            "commission_bps": category.commission_bps,
            "status": category.status,
            "sort": category.sort,
            "tenant_count": 0,
        },
        "类目已创建",
    )


@router.put("/service-categories/{category_id}", response_model=ApiResponse[dict])
async def update_service_category(
    category_id: int,
    payload: ServiceCategoryUpdate,
    _context=Depends(require_platform_permission("platform:tenant:manage")),
    db: AsyncSession = Depends(get_db),
):
    category = await category_service.get_or_404(db, category_id)
    updated = await category_service.update_category(
        db,
        category,
        name=payload.name,
        description=payload.description,
        commission_bps=payload.commission_bps,
        status=payload.status,
        sort=payload.sort,
    )
    await db.commit()
    await db.refresh(updated)
    return ok(
        {
            "id": updated.id,
            "code": updated.code,
            "name": updated.name,
            "description": updated.description,
            "commission_bps": updated.commission_bps,
            "status": updated.status,
            "sort": updated.sort,
        },
        "类目已更新",
    )


@router.put("/tenants/{tenant_id}/service-category", response_model=ApiResponse[dict])
async def assign_tenant_category(
    tenant_id: int,
    payload: TenantCategoryAssign,
    _context=Depends(require_platform_permission("platform:tenant:manage")),
    db: AsyncSession = Depends(get_db),
):
    from app.models.tenant import Tenant

    tenant = await db.get(Tenant, tenant_id)
    if tenant is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="租户不存在")
    updated = await category_service.assign_tenant(db, tenant, payload.service_category_id)
    await db.commit()
    return ok(
        {"tenant_id": updated.id, "service_category_id": updated.service_category_id},
        "租户归类已更新",
    )
