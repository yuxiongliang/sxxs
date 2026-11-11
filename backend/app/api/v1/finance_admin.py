"""Finance administration: commission rules, payout review, settlement batches."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_permission
from app.core.response import ok
from app.models.finance import CommissionRule
from app.schemas.common import ApiResponse
from app.schemas.finance import (
    CommissionPreviewOut,
    CommissionPreviewRequest,
    CommissionRuleCreate,
    CommissionRuleOut,
    CommissionRuleUpdate,
    PayoutOut,
    PayoutRejectRequest,
    SettlementBatchCreate,
    SettlementBatchOut,
)
from app.services import audit as audit_service
from app.services import finance as finance_service
from app.services.auth import AuthContext

router = APIRouter(prefix="/admin", tags=["财务中心"])


# --------------------------------------------------------------------------- #
# Commission rules
# --------------------------------------------------------------------------- #


@router.get("/commission-rules", response_model=ApiResponse[list[CommissionRuleOut]])
async def list_commission_rules(
    context: AuthContext = Depends(require_permission("commission:read")),
    db: AsyncSession = Depends(get_db),
):
    rules = await finance_service.list_commission_rules(db, context.tenant.id)
    return ok([CommissionRuleOut.model_validate(rule) for rule in rules])


@router.post("/commission-rules", response_model=ApiResponse[CommissionRuleOut])
async def create_commission_rule(
    payload: CommissionRuleCreate,
    context: AuthContext = Depends(require_permission("commission:manage")),
    db: AsyncSession = Depends(get_db),
):
    if payload.rate_bps == 0 and payload.fixed_fee_cents == 0:
        raise HTTPException(status_code=400, detail="佣金比例与固定费用不能同时为 0")
    rule = CommissionRule(
        tenant_id=context.tenant.id,
        name=payload.name,
        category_id=payload.category_id,
        seller_id=payload.seller_id,
        rate_bps=payload.rate_bps,
        fixed_fee_cents=payload.fixed_fee_cents,
        priority=payload.priority,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        status=payload.status,
    )
    db.add(rule)
    await db.flush()
    await audit_service.record(
        db,
        action=audit_service.ACTION_COMMISSION_RULE_CREATED,
        tenant_id=context.tenant.id,
        actor_id=context.user.id,
        target_type="commission_rule",
        target_id=rule.id,
        after={
            "name": rule.name,
            "rate_bps": rule.rate_bps,
            "fixed_fee_cents": rule.fixed_fee_cents,
            "seller_id": rule.seller_id,
            "category_id": rule.category_id,
        },
    )
    await db.commit()
    await db.refresh(rule)
    return ok(CommissionRuleOut.model_validate(rule), "佣金规则已创建")


@router.put("/commission-rules/{rule_id}", response_model=ApiResponse[CommissionRuleOut])
async def update_commission_rule(
    rule_id: int,
    payload: CommissionRuleUpdate,
    context: AuthContext = Depends(require_permission("commission:manage")),
    db: AsyncSession = Depends(get_db),
):
    rule = await db.get(CommissionRule, rule_id)
    if rule is None or rule.tenant_id != context.tenant.id:
        raise HTTPException(status_code=404, detail="佣金规则不存在")
    before = {"rate_bps": rule.rate_bps, "fixed_fee_cents": rule.fixed_fee_cents}
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, key, value)
    await audit_service.record(
        db,
        action=audit_service.ACTION_COMMISSION_RULE_UPDATED,
        tenant_id=context.tenant.id,
        actor_id=context.user.id,
        target_type="commission_rule",
        target_id=rule.id,
        before=before,
        after={"rate_bps": rule.rate_bps, "fixed_fee_cents": rule.fixed_fee_cents},
    )
    await db.commit()
    await db.refresh(rule)
    return ok(CommissionRuleOut.model_validate(rule), "佣金规则已更新")


@router.delete("/commission-rules/{rule_id}", response_model=ApiResponse[None])
async def delete_commission_rule(
    rule_id: int,
    context: AuthContext = Depends(require_permission("commission:manage")),
    db: AsyncSession = Depends(get_db),
):
    rule = await db.get(CommissionRule, rule_id)
    if rule is None or rule.tenant_id != context.tenant.id:
        raise HTTPException(status_code=404, detail="佣金规则不存在")
    await audit_service.record(
        db,
        action=audit_service.ACTION_COMMISSION_RULE_DELETED,
        tenant_id=context.tenant.id,
        actor_id=context.user.id,
        target_type="commission_rule",
        target_id=rule.id,
        before={"name": rule.name, "rate_bps": rule.rate_bps},
    )
    await db.delete(rule)
    await db.commit()
    return ok(None, "佣金规则已删除")


@router.post("/commission-rules/preview", response_model=ApiResponse[CommissionPreviewOut])
async def preview_commission(
    payload: CommissionPreviewRequest,
    context: AuthContext = Depends(require_permission("commission:read")),
    db: AsyncSession = Depends(get_db),
):
    rule = await finance_service.resolve_commission_rule(
        db, context.tenant.id, payload.seller_id, payload.category_id
    )
    commission = finance_service.compute_commission(payload.subtotal_cents, rule)
    return ok(
        CommissionPreviewOut(
            rule_id=rule.id if rule else None,
            rule_name=rule.name if rule else None,
            rate_bps=finance_service.effective_rate_bps(rule),
            fixed_fee_cents=finance_service.effective_fixed_fee(rule),
            subtotal_cents=payload.subtotal_cents,
            commission_cents=commission,
            payable_to_seller_cents=payload.subtotal_cents - commission,
        )
    )


# --------------------------------------------------------------------------- #
# Payout review (提现审核)
# --------------------------------------------------------------------------- #


@router.get("/payouts", response_model=ApiResponse[list[PayoutOut]])
async def list_payouts(
    status: str | None = Query(default=None),
    context: AuthContext = Depends(require_permission("payout:read")),
    db: AsyncSession = Depends(get_db),
):
    payouts = await finance_service.list_payouts(db, context, status)
    return ok([PayoutOut.model_validate(item) for item in payouts])


@router.post("/payouts/{payout_id}/approve", response_model=ApiResponse[PayoutOut])
async def approve_payout(
    payout_id: int,
    context: AuthContext = Depends(require_permission("payout:manage")),
    db: AsyncSession = Depends(get_db),
):
    payout = await finance_service.review_payout(db, context, payout_id, "approve")
    return ok(PayoutOut.model_validate(payout), "提现已审核通过")


@router.post("/payouts/{payout_id}/reject", response_model=ApiResponse[PayoutOut])
async def reject_payout(
    payout_id: int,
    payload: PayoutRejectRequest,
    context: AuthContext = Depends(require_permission("payout:manage")),
    db: AsyncSession = Depends(get_db),
):
    payout = await finance_service.review_payout(
        db, context, payout_id, "reject", payload.reason
    )
    return ok(PayoutOut.model_validate(payout), "提现已驳回")


@router.post("/payouts/{payout_id}/pay", response_model=ApiResponse[PayoutOut])
async def pay_payout(
    payout_id: int,
    context: AuthContext = Depends(require_permission("payout:manage")),
    db: AsyncSession = Depends(get_db),
):
    payout = await finance_service.mark_payout_paid(db, context, payout_id)
    return ok(PayoutOut.model_validate(payout), "提现已打款")


# --------------------------------------------------------------------------- #
# Settlement batches (结算批次)
# --------------------------------------------------------------------------- #


@router.get("/settlement-batches", response_model=ApiResponse[list[SettlementBatchOut]])
async def list_settlement_batches(
    context: AuthContext = Depends(require_permission("payout:read")),
    db: AsyncSession = Depends(get_db),
):
    batches = await finance_service.list_settlement_batches(db, context)
    return ok([SettlementBatchOut.model_validate(item) for item in batches])


@router.post("/settlement-batches", response_model=ApiResponse[SettlementBatchOut])
async def create_settlement_batch(
    payload: SettlementBatchCreate,
    context: AuthContext = Depends(require_permission("payout:manage")),
    db: AsyncSession = Depends(get_db),
):
    batch = await finance_service.create_settlement_batch(
        db, context, payload.period_start, payload.period_end, payload.note
    )
    return ok(SettlementBatchOut.model_validate(batch), "结算批次已创建")


@router.post(
    "/settlement-batches/{batch_id}/confirm", response_model=ApiResponse[SettlementBatchOut]
)
async def confirm_settlement_batch(
    batch_id: int,
    context: AuthContext = Depends(require_permission("payout:manage")),
    db: AsyncSession = Depends(get_db),
):
    batch = await finance_service.confirm_settlement_batch(db, context, batch_id)
    return ok(SettlementBatchOut.model_validate(batch), "结算批次已确认")


@router.post(
    "/settlement-batches/{batch_id}/pay", response_model=ApiResponse[SettlementBatchOut]
)
async def pay_settlement_batch(
    batch_id: int,
    context: AuthContext = Depends(require_permission("payout:manage")),
    db: AsyncSession = Depends(get_db),
):
    batch = await finance_service.pay_settlement_batch(db, context, batch_id)
    return ok(SettlementBatchOut.model_validate(batch), "结算批次已打款")
