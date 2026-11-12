"""平台向租户的抽佣台账（按月汇总，只读）。

口径（2026-11-12 与用户确认）：

* 基数 = 该租户当月**已支付**订单金额（orders.paid_at 落在当月，取 payable_amount_cents，
  与经营看板的 GMV 口径一致）；
* 比例 = 租户所属业务类目的 commission_bps（万分比）；
* **买断（lifetime）与自定义档期（custom）套餐的租户一律 0**，即使类目配了比例也不抽；
* 只出报表、不落账、不扣款：真正的收款动作需要单独的账务流程。
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import NON_RECURRING_PERIODS, Plan, TenantSubscription
from app.models.order import Order
from app.models.service_category import ServiceCategory
from app.models.tenant import Tenant


def month_window(month: str | None) -> tuple[datetime, datetime, str]:
    """把 YYYY-MM 解析成 [start, next_month) 的 UTC 区间；不传用当月。"""
    if month:
        try:
            start = datetime.strptime(month, "%Y-%m").replace(tzinfo=UTC)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="月份格式应为 YYYY-MM") from exc
    else:
        now = datetime.now(UTC)
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end, start.strftime("%Y-%m")


async def monthly_report(db: AsyncSession, month: str | None = None) -> dict:
    """每个租户一行：当月 GMV、类目比例、应抽佣、以及是否为买断/档期豁免。"""
    start, end, label = month_window(month)

    gmv_rows = (
        await db.execute(
            select(Order.tenant_id, func.coalesce(func.sum(Order.payable_amount_cents), 0))
            .where(
                Order.paid_at.is_not(None),
                Order.paid_at >= start,
                Order.paid_at < end,
            )
            .group_by(Order.tenant_id)
        )
    ).all()
    gmv_by_tenant = {tenant_id: int(total) for tenant_id, total in gmv_rows}

    tenants = list((await db.scalars(select(Tenant).order_by(Tenant.id))).all())
    categories = {row.id: row for row in (await db.scalars(select(ServiceCategory))).all()}
    subscriptions = {
        row.tenant_id: row for row in (await db.scalars(select(TenantSubscription))).all()
    }
    plan_periods = {row.id: row.period for row in (await db.scalars(select(Plan))).all()}

    rows = []
    total_commission = 0
    for tenant in tenants:
        category = categories.get(tenant.service_category_id or 0)
        subscription = subscriptions.get(tenant.id)
        period = plan_periods.get(subscription.plan_id) if subscription else None
        waived = period in NON_RECURRING_PERIODS
        gmv = gmv_by_tenant.get(tenant.id, 0)
        rate_bps = 0 if waived or category is None else category.commission_bps
        commission = gmv * rate_bps // 10000
        total_commission += commission
        rows.append(
            {
                "tenant_id": tenant.id,
                "tenant_name": tenant.display_name or tenant.name,
                "tenant_slug": tenant.slug,
                "service_category": (
                    {
                        "id": category.id,
                        "name": category.name,
                        "commission_bps": category.commission_bps,
                    }
                    if category is not None
                    else None
                ),
                "plan_period": period,
                "waived": waived,
                "gmv_cents": gmv,
                "rate_bps": rate_bps,
                "commission_cents": commission,
            }
        )

    return {
        "month": label,
        "window_start": start,
        "window_end": end,
        "total_gmv_cents": sum(row["gmv_cents"] for row in rows),
        "total_commission_cents": total_commission,
        "rows": rows,
    }
