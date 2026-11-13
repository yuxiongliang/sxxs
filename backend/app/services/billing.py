"""SaaS billing: plans, subscriptions, invoices, usage/quota, tenant lifecycle.

Three layers of enforcement:

1. **Tenant status** — ``suspended`` tenants fail closed in ``context_from_payload``
   (403 「租户不可用」), so suspending a tenant straight away blocks every API call.
2. **Feature gates** — ``plan.features`` decides which modules a tenant can use.
   A missing key or ``None`` means unlimited.
3. **Feature flags** — ``plan.features`` lists unlocked capability keys, exposed to
   the tenant so the UI can hide unsupported modules.

Usage is *computed live* from business tables rather than stored, so the numbers
can never drift from reality.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import (
    NON_RECURRING_PERIODS,
    PERIOD_DAYS,
    Invoice,
    Plan,
    TenantSubscription,
)
from app.models.catalog import Product
from app.models.order import Order
from app.models.tenant import TenantMember
from app.services import audit as audit_service
from app.services.auth import AuthContext

# 新开通租户默认用买断套餐（平台只卖这一个）；
# 欠费降级的落点仍是 free（下架但保留行），两者不能混用同一个常量。
DEFAULT_PLAN_CODE = "buyout"
DOWNGRADE_PLAN_CODE = "free"
# Days a tenant keeps full service after an invoice falls due before downgrading.
DEFAULT_GRACE_DAYS = 7


# --------------------------------------------------------------------------- #
# Plans
# --------------------------------------------------------------------------- #


async def list_plans(db: AsyncSession, include_archived: bool = False) -> list[Plan]:
    stmt = select(Plan)
    if not include_archived:
        stmt = stmt.where(Plan.status == "active")
    return list((await db.scalars(stmt.order_by(Plan.sort, Plan.id))).all())


async def get_plan_by_code(db: AsyncSession, code: str) -> Plan | None:
    return (await db.scalars(select(Plan).where(Plan.code == code))).first()


async def _get_plan(db: AsyncSession, plan_id: int) -> Plan:
    plan = await db.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="套餐不存在")
    return plan


# --------------------------------------------------------------------------- #
# Subscriptions
# --------------------------------------------------------------------------- #


async def get_subscription(db: AsyncSession, tenant_id: int) -> TenantSubscription | None:
    return (
        await db.scalars(
            select(TenantSubscription).where(TenantSubscription.tenant_id == tenant_id)
        )
    ).first()


async def _default_plan(db: AsyncSession) -> Plan | None:
    plan = await get_plan_by_code(db, DEFAULT_PLAN_CODE)
    if plan is not None:
        return plan
    plans = await list_plans(db)
    return plans[0] if plans else None


# 永久套餐用一个极远的到期时间表示，避免 current_period_end 变成可空到处判空
LIFETIME_END = datetime(9999, 12, 31, tzinfo=UTC)


def _term_window(plan: Plan, now: datetime, trial_days: int) -> tuple[datetime, datetime]:
    """算出这次订阅的起止时间。

    * lifetime —— 永久：起点 now，终点 LIFETIME_END；
    * custom   —— 用管理员在套餐上填的档期，缺任一端直接报错，不猜；
    * 其它     —— 试用天数优先，否则一个计费周期。
    """
    if plan.period == "lifetime":
        return now, LIFETIME_END
    if plan.period == "custom":
        if plan.starts_at is None or plan.ends_at is None:
            raise HTTPException(status_code=400, detail="自定义档期套餐缺少开始或到期时间")
        return plan.starts_at, plan.ends_at
    # 管理员填了「时长（月）」就按 N × 30 天算；否则退回 period 的默认天数
    days = trial_days or (
        plan.duration_months * 30 if plan.duration_months else PERIOD_DAYS.get(plan.period, 30)
    )
    return now, now + timedelta(days=days)


async def start_subscription(
    db: AsyncSession,
    tenant_id: int,
    plan_id: int | None = None,
    *,
    trial: bool = True,
    commit: bool = True,
) -> TenantSubscription | None:
    """Attach a plan to a tenant (no-op when the plan catalogue is empty)."""
    plan = await _get_plan(db, plan_id) if plan_id else await _default_plan(db)
    if plan is None:
        return None

    now = datetime.now(UTC)
    # 永久买断 / 自定义档期套餐不允许试用：试用只对周期套餐有意义
    trial_days = plan.trial_days if trial and plan.period not in NON_RECURRING_PERIODS else 0
    period_start, period_end = _term_window(plan, now, trial_days)
    subscription = await get_subscription(db, tenant_id)
    if subscription is None:
        subscription = TenantSubscription(
            tenant_id=tenant_id,
            plan_id=plan.id,
            status="trialing" if trial_days else "active",
            current_period_start=period_start,
            current_period_end=period_end,
            trial_end=now + timedelta(days=trial_days) if trial_days else None,
        )
        db.add(subscription)
    else:
        subscription.plan_id = plan.id
        subscription.status = "trialing" if trial_days else "active"
        subscription.current_period_start = period_start
        subscription.current_period_end = period_end
        subscription.trial_end = now + timedelta(days=trial_days) if trial_days else None
        subscription.cancel_at_period_end = False

    await db.flush()
    if commit:
        await db.commit()
        await db.refresh(subscription)
    return subscription


async def change_plan(db: AsyncSession, tenant_id: int, plan_id: int) -> TenantSubscription:
    plan = await _get_plan(db, plan_id)
    subscription = await get_subscription(db, tenant_id)
    if subscription is None:
        created = await start_subscription(db, tenant_id, plan.id, trial=False)
        assert created is not None
        return created

    subscription.plan_id = plan.id
    # Switching to a paid plan lifts a trial restriction immediately.
    if subscription.status == "trialing" and not plan.trial_days:
        subscription.status = "active"
    await db.commit()
    await db.refresh(subscription)
    return subscription


def _invoice_no(prefix: str = "INV") -> str:
    return f"{prefix}{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}{secrets.token_hex(2).upper()}"


async def renew_subscription(
    db: AsyncSession, tenant_id: int, days: int | None = None
) -> tuple[TenantSubscription, Invoice | None]:
    """Extend the current term and issue a pending invoice for the new term."""
    subscription = await get_subscription(db, tenant_id)
    if subscription is None:
        raise HTTPException(status_code=404, detail="该租户没有订阅")
    plan = await db.get(Plan, subscription.plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="套餐不存在")

    if plan.period in NON_RECURRING_PERIODS:
        # 买断/档期套餐没有「下一个账期」，续费会凭空造一笔不该收的账单
        raise HTTPException(status_code=400, detail="该套餐是永久买断或自定义档期，不按周期续费")

    now = datetime.now(UTC)
    period_days = days or PERIOD_DAYS.get(plan.period, 30)
    start = max(subscription.current_period_end, now)
    end = start + timedelta(days=period_days)

    invoice = Invoice(
        tenant_id=tenant_id,
        subscription_id=subscription.id,
        invoice_no=_invoice_no(),
        amount_cents=plan.price_cents,
        status="pending",
        period_start=start,
        period_end=end,
        due_at=start,
        note=f"续费 {plan.name}",
    )
    db.add(invoice)

    subscription.current_period_start = start
    subscription.current_period_end = end
    subscription.status = "active"
    subscription.trial_end = None
    await db.commit()
    await db.refresh(subscription)
    await db.refresh(invoice)
    return subscription, invoice


# --------------------------------------------------------------------------- #
# Invoices
# --------------------------------------------------------------------------- #


async def list_invoices(
    db: AsyncSession, tenant_id: int | None = None, status: str | None = None
) -> list[Invoice]:
    stmt = select(Invoice)
    if tenant_id is not None:
        stmt = stmt.where(Invoice.tenant_id == tenant_id)
    if status:
        stmt = stmt.where(Invoice.status == status)
    return list((await db.scalars(stmt.order_by(Invoice.id.desc()))).all())


async def pay_invoice(db: AsyncSession, invoice_id: int) -> Invoice:
    invoice = await db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="账单不存在")
    if invoice.status != "pending":
        raise HTTPException(status_code=400, detail="该账单已处理")

    invoice.status = "paid"
    invoice.paid_at = datetime.now(UTC)

    subscription = (
        await db.get(TenantSubscription, invoice.subscription_id)
        if invoice.subscription_id
        else None
    )
    if subscription is not None and subscription.status in {"past_due", "trialing"}:
        subscription.status = "active"

    await db.commit()
    await db.refresh(invoice)
    return invoice


# --------------------------------------------------------------------------- #
# Recurring billing lifecycle (自动续费 / 欠费降级)
# --------------------------------------------------------------------------- #


def _append_note(invoice: Invoice, suffix: str) -> None:
    invoice.note = invoice.note + "；" + suffix if invoice.note else suffix


async def _overdue_invoice(
    db: AsyncSession, subscription: TenantSubscription, moment: datetime, grace_days: int
) -> Invoice | None:
    """The oldest pending invoice whose grace window has already closed."""
    cutoff = moment - timedelta(days=max(0, grace_days))
    return (
        await db.scalars(
            select(Invoice)
            .where(
                Invoice.subscription_id == subscription.id,
                Invoice.status == "pending",
                Invoice.due_at.is_not(None),
                Invoice.due_at <= cutoff,
            )
            .order_by(Invoice.id)
        )
    ).first()


async def _downgrade_to_free(
    db: AsyncSession,
    subscription: TenantSubscription,
    current_plan: Plan,
    free_plan: Plan,
    invoice: Invoice,
    moment: datetime,
) -> None:
    """Grace window closed: keep the tenant usable, but on the free plan."""
    previous_plan_id = subscription.plan_id
    subscription.plan_id = free_plan.id
    subscription.status = "active"
    subscription.cancel_at_period_end = False
    subscription.current_period_start = moment
    subscription.current_period_end = moment + timedelta(days=PERIOD_DAYS.get(free_plan.period, 30))
    invoice.status = "void"
    _append_note(invoice, "宽限期结束未收到款项，已降级到免费套餐")
    await audit_service.record(
        db,
        action=audit_service.ACTION_SUBSCRIPTION_DOWNGRADED,
        tenant_id=subscription.tenant_id,
        target_type="subscription",
        target_id=subscription.id,
        before={"plan_id": previous_plan_id, "status": "past_due"},
        after={
            "plan_id": free_plan.id,
            "status": "active",
            "voided_invoice": invoice.invoice_no,
            "unpaid_cents": invoice.amount_cents,
            "previous_plan": current_plan.code,
        },
    )


async def run_billing_cycle(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    grace_days: int | None = None,
    commit: bool = True,
) -> dict[str, int]:
    """Advance every subscription one step through its lifecycle.

    - trialing/active, term ended, paid plan   -> past_due + pending invoice
    - trialing/active, term ended, free plan   -> active (term rolled forward)
    - trialing/active, term ended, cancel flag -> cancelled
    - past_due, grace window spent             -> active on the free plan

    Idempotent: billing a term reserves it (current_period_end moves into the
    future), so re-running inside the same term is a no-op.
    """
    moment = now or datetime.now(UTC)
    grace = DEFAULT_GRACE_DAYS if grace_days is None else grace_days
    summary = {
        "scanned": 0,
        "invoiced": 0,
        "renewed": 0,
        "cancelled": 0,
        "downgraded": 0,
    }

    subscriptions = list((await db.scalars(select(TenantSubscription))).all())
    free_plan = await get_plan_by_code(db, DOWNGRADE_PLAN_CODE)

    for subscription in subscriptions:
        summary["scanned"] += 1
        plan = await db.get(Plan, subscription.plan_id)
        if plan is None:
            continue
        # 永久买断 / 自定义档期不参与周期计费：不开发票、不判欠费、不降级
        if plan.period in NON_RECURRING_PERIODS:
            continue

        if subscription.status == "past_due":
            overdue = await _overdue_invoice(db, subscription, moment, grace)
            if overdue is None or free_plan is None:
                continue
            await _downgrade_to_free(db, subscription, plan, free_plan, overdue, moment)
            summary["downgraded"] += 1
            continue

        if subscription.status not in {"trialing", "active"}:
            continue
        if subscription.current_period_end > moment:
            continue

        if subscription.cancel_at_period_end:
            previous_status = subscription.status
            subscription.status = "cancelled"
            await audit_service.record(
                db,
                action=audit_service.ACTION_SUBSCRIPTION_CANCELLED,
                tenant_id=subscription.tenant_id,
                target_type="subscription",
                target_id=subscription.id,
                before={"status": previous_status},
                after={"status": "cancelled", "plan_code": plan.code},
            )
            summary["cancelled"] += 1
            continue

        period_days = PERIOD_DAYS.get(plan.period, 30)
        start = max(subscription.current_period_end, moment)
        end = start + timedelta(days=period_days)
        subscription.current_period_start = start
        subscription.current_period_end = end

        if plan.price_cents <= 0:
            previous_status = subscription.status
            subscription.status = "active"
            await audit_service.record(
                db,
                action=audit_service.ACTION_SUBSCRIPTION_RENEWED,
                tenant_id=subscription.tenant_id,
                target_type="subscription",
                target_id=subscription.id,
                before={"status": previous_status},
                after={
                    "status": "active",
                    "plan_code": plan.code,
                    "period_end": end.isoformat(),
                },
            )
            summary["renewed"] += 1
            continue

        previous_status = subscription.status
        invoice = Invoice(
            tenant_id=subscription.tenant_id,
            subscription_id=subscription.id,
            invoice_no=_invoice_no(),
            amount_cents=plan.price_cents,
            status="pending",
            period_start=start,
            period_end=end,
            due_at=moment,
            note="自动续费 " + plan.name,
        )
        db.add(invoice)
        subscription.status = "past_due"
        await audit_service.record(
            db,
            action=audit_service.ACTION_SUBSCRIPTION_PAST_DUE,
            tenant_id=subscription.tenant_id,
            target_type="subscription",
            target_id=subscription.id,
            before={"status": previous_status},
            after={
                "status": "past_due",
                "plan_code": plan.code,
                "invoice_no": invoice.invoice_no,
                "amount_cents": invoice.amount_cents,
                "grace_days": grace,
            },
        )
        summary["invoiced"] += 1

    if commit:
        await db.commit()
    return summary


# --------------------------------------------------------------------------- #
# Usage
# --------------------------------------------------------------------------- #


def _month_start(now: datetime) -> datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def compute_usage(db: AsyncSession, tenant_id: int) -> dict[str, int]:
    """Live resource counts for a tenant."""
    products = (
        await db.scalar(select(func.count(Product.id)).where(Product.tenant_id == tenant_id)) or 0
    )
    members = (
        await db.scalar(
            select(func.count(TenantMember.id)).where(
                TenantMember.tenant_id == tenant_id,
                TenantMember.status == "active",
            )
        )
        or 0
    )
    orders_this_month = (
        await db.scalar(
            select(func.count(Order.id)).where(
                Order.tenant_id == tenant_id,
                Order.created_at >= _month_start(datetime.now(UTC)),
            )
        )
        or 0
    )
    return {
        "products": int(products),
        "members": int(members),
        "orders_this_month": int(orders_this_month),
    }


async def usage_report(db: AsyncSession, tenant_id: int) -> dict:
    """Usage joined with the plan's feature flags."""
    subscription = await get_subscription(db, tenant_id)
    plan = await db.get(Plan, subscription.plan_id) if subscription else None
    used = await compute_usage(db, tenant_id)

    now = datetime.now(UTC)
    return {
        "tenant_id": tenant_id,
        "plan": (
            {
                "id": plan.id,
                "code": plan.code,
                "name": plan.name,
                "price_cents": plan.price_cents,
                "period": plan.period,
                "features": plan.features or [],
            }
            if plan
            else None
        ),
        "subscription": (
            {
                "id": subscription.id,
                "status": subscription.status,
                "current_period_start": subscription.current_period_start,
                "current_period_end": subscription.current_period_end,
                "cancel_at_period_end": subscription.cancel_at_period_end,
                "trial_end": subscription.trial_end,
            }
            if subscription
            else None
        ),
        "used": used,
        "days_left": (
            max(0, (subscription.current_period_end - now).days) if subscription else None
        ),
    }


async def has_feature(db: AsyncSession, tenant_id: int, feature: str) -> bool:
    subscription = await get_subscription(db, tenant_id)
    if subscription is None:
        return True
    plan = await db.get(Plan, subscription.plan_id)
    if plan is None:
        return True
    features = plan.features or []
    return feature in features


async def tenant_context_owner(context: AuthContext) -> int:
    """Small helper so callers do not repeat ``context.tenant.id``."""
    return context.tenant.id
