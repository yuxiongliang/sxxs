"""平台级业务类目：增删改查 + 租户归类。

两条硬约束：

1. code 唯一且不可改（改名可以，改 code 会让历史口径断链）；
2. 归档（status=archived）而不是删除 —— 已有租户挂在上面，删了就没有抽佣依据了。
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service_category import ServiceCategory
from app.models.tenant import Tenant


async def list_categories(db: AsyncSession, include_archived: bool = False) -> list[dict]:
    """类目列表 + 每个类目下的租户数（运营最关心这个）。"""
    stmt = select(ServiceCategory)
    if not include_archived:
        stmt = stmt.where(ServiceCategory.status == "active")
    categories = list(
        (await db.scalars(stmt.order_by(ServiceCategory.sort, ServiceCategory.id))).all()
    )

    counted = (
        await db.execute(
            select(Tenant.service_category_id, func.count(Tenant.id)).group_by(
                Tenant.service_category_id
            )
        )
    ).all()
    tenant_counts = {category_id: total for category_id, total in counted if category_id}

    return [_serialize(category, tenant_counts.get(category.id, 0)) for category in categories]


def _serialize(category: ServiceCategory, tenant_count: int) -> dict:
    return {
        "id": category.id,
        "code": category.code,
        "name": category.name,
        "description": category.description,
        "commission_bps": category.commission_bps,
        "status": category.status,
        "sort": category.sort,
        "tenant_count": tenant_count,
    }


async def get_or_404(db: AsyncSession, category_id: int) -> ServiceCategory:
    category = await db.get(ServiceCategory, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="业务类目不存在")
    return category


async def create_category(
    db: AsyncSession,
    *,
    code: str,
    name: str,
    description: str,
    commission_bps: int,
    sort: int,
) -> ServiceCategory:
    exists = (await db.scalars(select(ServiceCategory).where(ServiceCategory.code == code))).first()
    if exists is not None:
        raise HTTPException(status_code=409, detail="类目编码已存在")
    category = ServiceCategory(
        code=code,
        name=name,
        description=description,
        commission_bps=commission_bps,
        sort=sort,
        status="active",
    )
    db.add(category)
    await db.flush()
    return category


async def update_category(
    db: AsyncSession,
    category: ServiceCategory,
    *,
    name: str | None,
    description: str | None,
    commission_bps: int | None,
    status: str | None,
    sort: int | None,
) -> ServiceCategory:
    if name is not None:
        category.name = name
    if description is not None:
        category.description = description
    if commission_bps is not None:
        category.commission_bps = commission_bps
    if status is not None:
        category.status = status
    if sort is not None:
        category.sort = sort
    await db.flush()
    return category


async def assign_tenant(db: AsyncSession, tenant: Tenant, category_id: int | None) -> Tenant:
    """给租户归类；category_id=None 表示取消归类。"""
    if category_id is not None:
        category = await get_or_404(db, category_id)
        if category.status != "active":
            raise HTTPException(status_code=400, detail="该类目已归档，不能分配新租户")
    tenant.service_category_id = category_id
    await db.flush()
    return tenant
