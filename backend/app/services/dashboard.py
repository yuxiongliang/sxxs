"""经营看板聚合：把真实业务表算成 KPI / 趋势 / 排行。

设计要点：

* 只读聚合，不建冗余计数表 —— 数字永远等于业务表本身，不会漂移。
* 时间按**业务时区**切日（默认 Asia/Shanghai）。按 UTC 切日会让每天有 8 小时
  的「今天」算错。
* GMV 只统计已支付订单（paid_at 非空）；未支付订单只体现在
  pending_payment_orders 里，绝不进收入。
* 所有查询强制带 tenant_id，跨租户永远看不到彼此的数字。
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.catalog import Product
from app.models.finance import Payout
from app.models.im import ImReport
from app.models.order import Order, OrderItem
from app.models.permission import MemberRole
from app.models.role import Role
from app.models.seller import Seller
from app.models.tenant import TenantMember
from app.services import billing as billing_service

TOP_PRODUCT_LIMIT = 5


def _tz() -> ZoneInfo:
    return ZoneInfo(settings.business_timezone)


def _today() -> date:
    return datetime.now(UTC).astimezone(_tz()).date()


def _day_start(day: date) -> datetime:
    """The UTC instant at which the given business day begins."""
    local = datetime.combine(day, datetime.min.time(), tzinfo=_tz())
    return local.astimezone(UTC)


def _range_start(days: int) -> datetime:
    return _day_start(_today() - timedelta(days=days - 1))


async def _gmv_since(db: AsyncSession, tenant_id: int, start: datetime | None = None) -> int:
    stmt = select(func.coalesce(func.sum(Order.payable_amount_cents), 0)).where(
        Order.tenant_id == tenant_id,
        Order.paid_at.is_not(None),
    )
    if start is not None:
        stmt = stmt.where(Order.paid_at >= start)
    return int(await db.scalar(stmt) or 0)


async def _orders_since(db: AsyncSession, tenant_id: int, start: datetime | None = None) -> int:
    stmt = select(func.count(Order.id)).where(Order.tenant_id == tenant_id)
    if start is not None:
        stmt = stmt.where(Order.created_at >= start)
    return int(await db.scalar(stmt) or 0)


async def _new_buyers_since(db: AsyncSession, tenant_id: int, start: datetime | None = None) -> int:
    """Members holding the customer role -- admins/operators are not buyers."""
    stmt = (
        select(func.count(func.distinct(TenantMember.id)))
        .select_from(TenantMember)
        .join(MemberRole, MemberRole.member_id == TenantMember.id)
        .join(Role, Role.id == MemberRole.role_id)
        .where(TenantMember.tenant_id == tenant_id, Role.code == "customer")
    )
    if start is not None:
        stmt = stmt.where(TenantMember.created_at >= start)
    return int(await db.scalar(stmt) or 0)


def _local_day(column):
    """date_trunc(day) applied in the business time zone."""
    return func.date_trunc("day", func.timezone(settings.business_timezone, column))


async def _daily_gmv(db: AsyncSession, tenant_id: int, days: int) -> dict[date, int]:
    # 语句内联在 execute() 处：所有值都是绑定参数（编译结果为
    # WHERE orders.tenant_id = %(tenant_id_1)s），不存在字符串拼接。
    bucket = _local_day(Order.paid_at)
    rows = list(
        (
            await db.execute(
                select(
                    bucket.label("day"),
                    func.coalesce(func.sum(Order.payable_amount_cents), 0),
                )
                .where(
                    Order.tenant_id == tenant_id,
                    Order.paid_at.is_not(None),
                    Order.paid_at >= _range_start(days),
                )
                .group_by(bucket)
            )
        ).all()
    )
    return {row[0].date(): int(row[1]) for row in rows}


async def _daily_orders(db: AsyncSession, tenant_id: int, days: int) -> dict[date, int]:
    bucket = _local_day(Order.created_at)
    rows = list(
        (
            await db.execute(
                select(bucket.label("day"), func.count(Order.id))
                .where(
                    Order.tenant_id == tenant_id,
                    Order.created_at >= _range_start(days),
                )
                .group_by(bucket)
            )
        ).all()
    )
    return {row[0].date(): int(row[1]) for row in rows}


async def _count_where(db: AsyncSession, model, *conditions) -> int:
    stmt = select(func.count(model.id)).where(*conditions)
    return int(await db.scalar(stmt) or 0)


async def _top_products(db: AsyncSession, tenant_id: int, days: int) -> list[dict]:
    quantity = func.sum(OrderItem.quantity)
    gmv = func.sum(OrderItem.subtotal_cents)
    rows = list(
        (
            await db.execute(
                select(OrderItem.product_id, OrderItem.product_name, quantity, gmv)
                .join(Order, Order.id == OrderItem.order_id)
                .where(
                    OrderItem.tenant_id == tenant_id,
                    Order.paid_at.is_not(None),
                    Order.paid_at >= _range_start(days),
                )
                .group_by(OrderItem.product_id, OrderItem.product_name)
                .order_by(quantity.desc(), gmv.desc())
                .limit(TOP_PRODUCT_LIMIT)
            )
        ).all()
    )
    return [
        {
            "product_id": row[0],
            "name": row[1],
            "quantity": int(row[2] or 0),
            "gmv_cents": int(row[3] or 0),
        }
        for row in rows
    ]


async def _order_status(db: AsyncSession, tenant_id: int) -> list[dict]:
    rows = list(
        (
            await db.execute(
                select(Order.status, func.count(Order.id))
                .where(Order.tenant_id == tenant_id)
                .group_by(Order.status)
                .order_by(func.count(Order.id).desc(), Order.status)
            )
        ).all()
    )
    return [{"status": row[0], "count": int(row[1])} for row in rows if int(row[1]) > 0]


async def _usage(db: AsyncSession, tenant_id: int) -> dict:
    report = await billing_service.usage_report(db, tenant_id)
    plan = report.get("plan") or {}
    quotas = report.get("quotas") or {}
    used = report.get("used") or {}
    subscription = report.get("subscription") or {}
    return {
        "plan": plan.get("code"),
        "plan_name": plan.get("name"),
        "subscription_status": subscription.get("status"),
        "products_used": int(used.get("products", 0)),
        "products_quota": quotas.get("products"),
        "members_used": int(used.get("members", 0)),
        "members_quota": quotas.get("members"),
        "days_left": report.get("days_left"),
    }


async def overview(db: AsyncSession, tenant_id: int, days: int = 30) -> dict:
    """KPIs, daily trend, status split and rankings for one tenant."""
    today = _today()
    today_start = _day_start(today)
    yesterday_start = _day_start(today - timedelta(days=1))

    gmv_by_day = await _daily_gmv(db, tenant_id, days)
    orders_by_day = await _daily_orders(db, tenant_id, days)
    trend = []
    for offset in range(days - 1, -1, -1):
        day = today - timedelta(days=offset)
        trend.append(
            {
                "date": day.isoformat(),
                "gmv_cents": gmv_by_day.get(day, 0),
                "orders": orders_by_day.get(day, 0),
            }
        )

    status_rows = await _order_status(db, tenant_id)
    total_orders = sum(row["count"] for row in status_rows)

    payouts_pending_count = await _count_where(
        db, Payout, Payout.tenant_id == tenant_id, Payout.status == "pending"
    )
    payouts_pending_cents = int(
        await db.scalar(
            select(func.coalesce(func.sum(Payout.amount_cents), 0)).where(
                Payout.tenant_id == tenant_id,
                Payout.status == "pending",
            )
        )
        or 0
    )

    kpi = {
        "gmv_today_cents": await _gmv_since(db, tenant_id, today_start),
        "gmv_yesterday_cents": int(
            await db.scalar(
                select(func.coalesce(func.sum(Order.payable_amount_cents), 0)).where(
                    Order.tenant_id == tenant_id,
                    Order.paid_at.is_not(None),
                    Order.paid_at >= yesterday_start,
                    Order.paid_at < today_start,
                )
            )
            or 0
        ),
        "orders_today": await _orders_since(db, tenant_id, today_start),
        "orders_yesterday": int(
            await db.scalar(
                select(func.count(Order.id)).where(
                    Order.tenant_id == tenant_id,
                    Order.created_at >= yesterday_start,
                    Order.created_at < today_start,
                )
            )
            or 0
        ),
        "new_buyers_today": await _new_buyers_since(db, tenant_id, today_start),
        "buyers_total": await _new_buyers_since(db, tenant_id),
        "pending_payment_orders": await _count_where(
            db,
            Order,
            Order.tenant_id == tenant_id,
            Order.status == "pending_payment",
        ),
        "products_on_sale": await _count_where(
            db, Product, Product.tenant_id == tenant_id, Product.status == "on_sale"
        ),
        "products_pending_review": await _count_where(
            db,
            Product,
            Product.tenant_id == tenant_id,
            Product.status == "pending_review",
        ),
        "sellers_active": await _count_where(
            db, Seller, Seller.tenant_id == tenant_id, Seller.status == "active"
        ),
        "sellers_pending": await _count_where(
            db, Seller, Seller.tenant_id == tenant_id, Seller.status == "pending"
        ),
        "payouts_pending_count": payouts_pending_count,
        "payouts_pending_cents": payouts_pending_cents,
        "im_reports_open": await _count_where(
            db, ImReport, ImReport.tenant_id == tenant_id, ImReport.status == "pending"
        ),
    }

    return {
        "range": {
            "days": days,
            "start": (today - timedelta(days=days - 1)).isoformat(),
            "end": today.isoformat(),
            "timezone": settings.business_timezone,
        },
        "kpi": kpi,
        "totals": {
            "orders": total_orders,
            "gmv_cents": await _gmv_since(db, tenant_id, _range_start(days)),
        },
        "trend": trend,
        "order_status": status_rows,
        "top_products": await _top_products(db, tenant_id, days),
        "usage": await _usage(db, tenant_id),
    }
