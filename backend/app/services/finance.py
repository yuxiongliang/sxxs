"""Commission, ledger, payout review and settlement batches.

Money rules in one place:

* **Commission** comes from ``commission_rules`` (basis points + fixed fee).
  Resolution order: seller+category > seller > category > tenant default, then
  highest ``priority``, then newest. A tenant with no rule falls back to
  ``DEFAULT_COMMISSION_BPS`` (10%).
* **账期 (hold period)**: money from an order only becomes withdrawable once the
  seller_order is ``completed`` *and* ``settlement_hold_days`` have elapsed.
  Everything else is reported as ``pending_cents``.
* **提现审核**: ``pending`` -> ``approved`` / ``rejected`` -> ``paid``. A rejected
  payout is terminal and never leaves the ledger.
* **结算批次**: a batch sweeps ``approved`` payouts of an accounting period and
  moves them to ``paid``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finance import (
    DEFAULT_COMMISSION_BPS,
    CommissionRule,
    LedgerEntry,
    Payout,
    SettlementBatch,
)
from app.models.order import SellerOrder
from app.models.seller import Seller
from app.models.tenant import Tenant
from app.services import audit as audit_service
from app.services.auth import AuthContext

# --------------------------------------------------------------------------- #
# Commission rules
# --------------------------------------------------------------------------- #


async def resolve_commission_rule(
    db: AsyncSession,
    tenant_id: int,
    seller_id: int | None,
    category_id: int | None,
    at: datetime | None = None,
) -> CommissionRule | None:
    """Pick the most specific active rule for this order."""
    moment = at or datetime.now(UTC)
    rules = list(
        (
            await db.scalars(
                select(CommissionRule).where(
                    CommissionRule.tenant_id == tenant_id,
                    CommissionRule.status == "active",
                )
            )
        ).all()
    )

    def _in_window(rule: CommissionRule) -> bool:
        if rule.effective_from and rule.effective_from > moment:
            return False
        return not (rule.effective_to and rule.effective_to < moment)

    def _specificity(rule: CommissionRule) -> tuple[int, int, int]:
        score = 0
        if rule.seller_id is not None:
            score += 2
        if rule.category_id is not None:
            score += 1
        return (score, rule.priority, rule.id)

    candidates = [
        rule
        for rule in rules
        if _in_window(rule)
        and (rule.seller_id is None or rule.seller_id == seller_id)
        and (rule.category_id is None or rule.category_id == category_id)
    ]
    if not candidates:
        return None
    return max(candidates, key=_specificity)


def effective_rate_bps(rule: CommissionRule | None) -> int:
    return rule.rate_bps if rule is not None else DEFAULT_COMMISSION_BPS


def effective_fixed_fee(rule: CommissionRule | None) -> int:
    return rule.fixed_fee_cents if rule is not None else 0


def compute_commission(subtotal_cents: int, rule: CommissionRule | None) -> int:
    """Commission in cents, rounding down in favour of the seller."""
    rate = effective_rate_bps(rule)
    commission = subtotal_cents * rate // 10_000 + effective_fixed_fee(rule)
    # Never let fees exceed the goods amount.
    return max(0, min(commission, subtotal_cents))


async def list_commission_rules(db: AsyncSession, tenant_id: int) -> list[CommissionRule]:
    return list(
        (
            await db.scalars(
                select(CommissionRule)
                .where(CommissionRule.tenant_id == tenant_id)
                .order_by(CommissionRule.priority.desc(), CommissionRule.id.desc())
            )
        ).all()
    )


async def ensure_default_rule(db: AsyncSession, tenant_id: int) -> CommissionRule:
    """Guarantee a tenant-wide default rule exists."""
    rule = await resolve_commission_rule(db, tenant_id, None, None)
    if rule is not None:
        return rule
    rule = CommissionRule(
        tenant_id=tenant_id,
        name="默认佣金规则",
        rate_bps=DEFAULT_COMMISSION_BPS,
        fixed_fee_cents=0,
        priority=0,
        status="active",
    )
    db.add(rule)
    await db.flush()
    return rule


# --------------------------------------------------------------------------- #
# Ledger
# --------------------------------------------------------------------------- #


async def record_order_ledger(db: AsyncSession, seller_order: SellerOrder) -> None:
    entries = [
        ("sale", seller_order.goods_amount_cents, f"sale:{seller_order.id}"),
        ("commission", -seller_order.commission_amount_cents, f"commission:{seller_order.id}"),
    ]
    for entry_type, amount, key in entries:
        exists = (
            await db.scalars(select(LedgerEntry).where(LedgerEntry.idempotency_key == key))
        ).first()
        if exists is None:
            db.add(
                LedgerEntry(
                    tenant_id=seller_order.tenant_id,
                    seller_id=seller_order.seller_id,
                    order_id=seller_order.order_id,
                    seller_order_id=seller_order.id,
                    type=entry_type,
                    amount_cents=amount,
                    idempotency_key=key,
                )
            )


async def record_refund_ledger(
    db: AsyncSession,
    seller_order: SellerOrder,
    refund_id: int,
    refund_amount_cents: int,
) -> int:
    """Reverse the goods *and* the matching commission slice of a refund.

    Only orders that were actually paid have ledger entries to reverse: refunding
    an unpaid order must not invent a negative balance. Returns the commission
    handed back to the seller (0 when nothing was ever charged).
    """
    credited = (
        await db.scalars(
            select(LedgerEntry).where(LedgerEntry.idempotency_key == f"sale:{seller_order.id}")
        )
    ).first()
    if credited is None:
        return 0

    goods = seller_order.goods_amount_cents
    commission = seller_order.commission_amount_cents
    # Proportional floor: a full refund always gives the whole commission back.
    commission_slice = commission * refund_amount_cents // goods if goods > 0 else 0

    entries = [
        ("refund", -refund_amount_cents, f"refund:{refund_id}"),
        ("refund_commission", commission_slice, f"refund_commission:{refund_id}"),
    ]
    for entry_type, amount, key in entries:
        exists = (
            await db.scalars(select(LedgerEntry).where(LedgerEntry.idempotency_key == key))
        ).first()
        if exists is None:
            db.add(
                LedgerEntry(
                    tenant_id=seller_order.tenant_id,
                    seller_id=seller_order.seller_id,
                    order_id=seller_order.order_id,
                    seller_order_id=seller_order.id,
                    type=entry_type,
                    amount_cents=amount,
                    idempotency_key=key,
                )
            )
    return commission_slice


async def _hold_days(db: AsyncSession, tenant_id: int) -> int:
    tenant = await db.get(Tenant, tenant_id)
    return tenant.settlement_hold_days if tenant is not None else 7


async def seller_ledger(db: AsyncSession, context: AuthContext, seller_id: int) -> dict:
    seller = await db.get(Seller, seller_id)
    if seller is None or seller.tenant_id != context.tenant.id:
        raise HTTPException(status_code=404, detail="卖家不存在")

    hold_days = await _hold_days(db, context.tenant.id)
    cutoff = datetime.now(UTC) - timedelta(days=hold_days)

    entries = list(
        (
            await db.scalars(
                select(LedgerEntry)
                .where(
                    LedgerEntry.tenant_id == context.tenant.id,
                    LedgerEntry.seller_id == seller_id,
                )
                .order_by(LedgerEntry.id.desc())
            )
        ).all()
    )

    gross_available = 0
    gross_pending = 0
    paid_out = 0

    annotated: list[dict] = []
    for item in entries:
        settlement = "settled"
        if item.type == "payout":
            paid_out += abs(item.amount_cents)
        elif item.seller_order_id is not None:
            seller_order = await db.get(SellerOrder, item.seller_order_id)
            completed_at = seller_order.completed_at if seller_order is not None else None
            settled = (
                seller_order is not None
                and seller_order.status in {"completed", "confirmed"}
                and completed_at is not None
                and completed_at <= cutoff
            )
            if settled:
                gross_available += item.amount_cents
                settlement = "available"
            else:
                gross_pending += item.amount_cents
                settlement = "pending"
        annotated.append(
            {
                "id": item.id,
                "type": item.type,
                "amount_cents": item.amount_cents,
                "seller_order_id": item.seller_order_id,
                "settlement": settlement,
                "created_at": item.created_at,
            }
        )

    # Money already paid out is deducted from the most settleable bucket first,
    # so the three numbers always reconcile: balance == available + pending.
    available = max(0, gross_available - paid_out)
    overflow = max(0, paid_out - gross_available)
    pending = max(0, gross_pending - overflow)
    balance = available + pending

    return {
        "seller_id": seller_id,
        "balance_cents": balance,
        "available_cents": available,
        "pending_cents": pending,
        "hold_days": hold_days,
        "entries": annotated,
    }


async def _settleable_balance(db: AsyncSession, context: AuthContext, seller_id: int) -> int:
    ledger = await seller_ledger(db, context, seller_id)
    return int(ledger["available_cents"])


# --------------------------------------------------------------------------- #
# Payouts (提现申请 + 审核)
# --------------------------------------------------------------------------- #


async def create_payout(
    db: AsyncSession,
    context: AuthContext,
    seller_id: int,
    requested_by: int | None = None,
) -> Payout:
    """Create a withdrawal request for the currently settleable balance."""
    available = await _settleable_balance(db, context, seller_id)
    if available <= 0:
        raise HTTPException(
            status_code=400,
            detail="可结算余额不足（订单完成且过账期后才可提现）",
        )

    in_flight = (
        await db.scalar(
            select(func.coalesce(func.sum(Payout.amount_cents), 0)).where(
                Payout.tenant_id == context.tenant.id,
                Payout.seller_id == seller_id,
                Payout.status.in_(("pending", "approved")),
            )
        )
        or 0
    )
    if int(in_flight) > 0:
        raise HTTPException(status_code=409, detail="已有待处理的提现申请")

    payout = Payout(
        tenant_id=context.tenant.id,
        seller_id=seller_id,
        amount_cents=available,
        status="pending",
        requested_by=requested_by,
    )
    db.add(payout)
    await db.flush()
    await audit_service.record(
        db,
        action=audit_service.ACTION_PAYOUT_REQUESTED,
        tenant_id=context.tenant.id,
        actor_id=context.user.id,
        target_type="payout",
        target_id=payout.id,
        after={"seller_id": seller_id, "amount_cents": available, "status": "pending"},
    )
    await db.commit()
    await db.refresh(payout)
    return payout


async def list_payouts(
    db: AsyncSession, context: AuthContext, status: str | None = None
) -> list[Payout]:
    stmt = select(Payout).where(Payout.tenant_id == context.tenant.id)
    if status:
        stmt = stmt.where(Payout.status == status)
    return list((await db.scalars(stmt.order_by(Payout.id.desc()))).all())


async def _get_payout(db: AsyncSession, context: AuthContext, payout_id: int) -> Payout:
    payout = await db.get(Payout, payout_id)
    if payout is None or payout.tenant_id != context.tenant.id:
        raise HTTPException(status_code=404, detail="提现申请不存在")
    return payout


async def review_payout(
    db: AsyncSession,
    context: AuthContext,
    payout_id: int,
    action: str,
    reason: str = "",
) -> Payout:
    payout = await _get_payout(db, context, payout_id)
    if payout.status != "pending":
        raise HTTPException(status_code=400, detail="该申请已处理")

    if action == "approve":
        payout.status = "approved"
        payout.reject_reason = ""
    else:
        payout.status = "rejected"
        payout.reject_reason = reason

    payout.reviewed_by = context.user.id
    payout.reviewed_at = datetime.now(UTC)
    await audit_service.record(
        db,
        action=(
            audit_service.ACTION_PAYOUT_APPROVED
            if action == "approve"
            else audit_service.ACTION_PAYOUT_REJECTED
        ),
        tenant_id=context.tenant.id,
        actor_id=context.user.id,
        target_type="payout",
        target_id=payout.id,
        before={"status": "pending"},
        after={"status": payout.status, "reason": reason, "amount_cents": payout.amount_cents},
    )
    await db.commit()
    await db.refresh(payout)
    return payout


async def mark_payout_paid(db: AsyncSession, context: AuthContext, payout_id: int) -> Payout:
    payout = await _get_payout(db, context, payout_id)
    if payout.status != "approved":
        raise HTTPException(status_code=400, detail="只有审核通过的提现可以打款")
    payout.status = "paid"
    payout.paid_at = datetime.now(UTC)

    db.add(
        LedgerEntry(
            tenant_id=payout.tenant_id,
            seller_id=payout.seller_id,
            type="payout",
            amount_cents=-payout.amount_cents,
            idempotency_key=f"payout:{payout.id}",
        )
    )
    await audit_service.record(
        db,
        action=audit_service.ACTION_PAYOUT_PAID,
        tenant_id=context.tenant.id,
        actor_id=context.user.id,
        target_type="payout",
        target_id=payout.id,
        before={"status": "approved"},
        after={"status": "paid", "amount_cents": payout.amount_cents},
    )
    await db.commit()
    await db.refresh(payout)
    return payout


# --------------------------------------------------------------------------- #
# Settlement batches (结算批次)
# --------------------------------------------------------------------------- #


def _batch_no(moment: datetime) -> str:
    return f"STL{moment.strftime('%Y%m%d%H%M%S%f')}"


async def create_settlement_batch(
    db: AsyncSession,
    context: AuthContext,
    period_start: datetime,
    period_end: datetime,
    note: str = "",
) -> SettlementBatch:
    if period_end <= period_start:
        raise HTTPException(status_code=400, detail="账期结束时间必须晚于开始时间")

    payouts = list(
        (
            await db.scalars(
                select(Payout).where(
                    Payout.tenant_id == context.tenant.id,
                    Payout.status == "approved",
                    Payout.settlement_batch_id.is_(None),
                )
            )
        ).all()
    )
    if not payouts:
        raise HTTPException(status_code=400, detail="没有可纳入批次的已审核提现")

    batch = SettlementBatch(
        tenant_id=context.tenant.id,
        batch_no=_batch_no(datetime.now(UTC)),
        period_start=period_start,
        period_end=period_end,
        status="draft",
        total_amount_cents=sum(item.amount_cents for item in payouts),
        seller_count=len({item.seller_id for item in payouts}),
        payout_count=len(payouts),
        created_by=context.user.id,
        note=note,
    )
    db.add(batch)
    await db.flush()
    for payout in payouts:
        payout.settlement_batch_id = batch.id
    await audit_service.record(
        db,
        action=audit_service.ACTION_SETTLEMENT_CREATED,
        tenant_id=context.tenant.id,
        actor_id=context.user.id,
        target_type="settlement_batch",
        target_id=batch.id,
        after={
            "batch_no": batch.batch_no,
            "total_amount_cents": batch.total_amount_cents,
            "payout_count": batch.payout_count,
        },
    )
    await db.commit()
    await db.refresh(batch)
    return batch


async def list_settlement_batches(db: AsyncSession, context: AuthContext) -> list[SettlementBatch]:
    return list(
        (
            await db.scalars(
                select(SettlementBatch)
                .where(SettlementBatch.tenant_id == context.tenant.id)
                .order_by(SettlementBatch.id.desc())
            )
        ).all()
    )


async def _get_batch(db: AsyncSession, context: AuthContext, batch_id: int) -> SettlementBatch:
    batch = await db.get(SettlementBatch, batch_id)
    if batch is None or batch.tenant_id != context.tenant.id:
        raise HTTPException(status_code=404, detail="结算批次不存在")
    return batch


async def confirm_settlement_batch(
    db: AsyncSession, context: AuthContext, batch_id: int
) -> SettlementBatch:
    batch = await _get_batch(db, context, batch_id)
    if batch.status != "draft":
        raise HTTPException(status_code=400, detail="只有草稿批次可以确认")
    batch.status = "confirmed"
    batch.confirmed_at = datetime.now(UTC)
    await audit_service.record(
        db,
        action=audit_service.ACTION_SETTLEMENT_CONFIRMED,
        tenant_id=context.tenant.id,
        actor_id=context.user.id,
        target_type="settlement_batch",
        target_id=batch.id,
        before={"status": "draft"},
        after={"status": "confirmed", "total_amount_cents": batch.total_amount_cents},
    )
    await db.commit()
    await db.refresh(batch)
    return batch


async def pay_settlement_batch(
    db: AsyncSession, context: AuthContext, batch_id: int
) -> SettlementBatch:
    batch = await _get_batch(db, context, batch_id)
    if batch.status != "confirmed":
        raise HTTPException(status_code=400, detail="只有已确认批次可以打款")

    payouts = list(
        (
            await db.scalars(
                select(Payout).where(
                    Payout.settlement_batch_id == batch.id,
                    Payout.status == "approved",
                )
            )
        ).all()
    )
    now = datetime.now(UTC)
    for payout in payouts:
        payout.status = "paid"
        payout.paid_at = now
        db.add(
            LedgerEntry(
                tenant_id=payout.tenant_id,
                seller_id=payout.seller_id,
                type="payout",
                amount_cents=-payout.amount_cents,
                idempotency_key=f"payout:{payout.id}",
            )
        )
        await audit_service.record(
            db,
            action=audit_service.ACTION_PAYOUT_PAID,
            tenant_id=payout.tenant_id,
            actor_id=context.user.id,
            target_type="payout",
            target_id=payout.id,
            before={"status": "approved"},
            after={
                "status": "paid",
                "amount_cents": payout.amount_cents,
                "settlement_batch_id": batch.id,
            },
        )

    batch.status = "paid"
    batch.paid_at = now
    await audit_service.record(
        db,
        action=audit_service.ACTION_SETTLEMENT_PAID,
        tenant_id=context.tenant.id,
        actor_id=context.user.id,
        target_type="settlement_batch",
        target_id=batch.id,
        before={"status": "confirmed"},
        after={
            "status": "paid",
            "total_amount_cents": batch.total_amount_cents,
            "payouts": len(payouts),
        },
    )
    await db.commit()
    await db.refresh(batch)
    return batch
