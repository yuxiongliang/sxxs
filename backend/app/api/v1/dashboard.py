"""经营看板聚合接口（真实数据，替代模板的假图表）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_permission
from app.core.response import ok
from app.services import dashboard as dashboard_service
from app.services.auth import AuthContext

router = APIRouter(prefix="/dashboard", tags=["经营看板"])


@router.get("/overview")
async def overview(
    days: int = Query(default=30, ge=7, le=90, description="趋势天数（7-90）"),
    context: AuthContext = Depends(require_permission("dashboard:read")),
    db: AsyncSession = Depends(get_db),
):
    """KPI + 日趋势 + 订单状态分布 + 商品排行 + 套餐用量。

    全部按当前租户聚合；GMV 只统计已支付订单；自然日按业务时区（默认
    Asia/Shanghai）切分。
    """
    return ok(await dashboard_service.overview(db, context.tenant.id, days))
