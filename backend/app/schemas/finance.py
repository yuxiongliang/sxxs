from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CommissionRuleCreate(BaseModel):
    name: str = Field(default="佣金规则", min_length=1, max_length=64)
    category_id: int | None = None
    seller_id: int | None = None
    rate_bps: int = Field(default=1000, ge=0, le=10_000)
    fixed_fee_cents: int = Field(default=0, ge=0)
    priority: int = Field(default=0, ge=0, le=100)
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    status: str = Field(default="active", pattern="^(active|disabled)$")


class CommissionRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    category_id: int | None = None
    seller_id: int | None = None
    rate_bps: int | None = Field(default=None, ge=0, le=10_000)
    fixed_fee_cents: int | None = Field(default=None, ge=0)
    priority: int | None = Field(default=None, ge=0, le=100)
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    status: str | None = Field(default=None, pattern="^(active|disabled)$")


class CommissionRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category_id: int | None = None
    seller_id: int | None = None
    rate_bps: int
    fixed_fee_cents: int
    priority: int
    status: str


class CommissionPreviewRequest(BaseModel):
    seller_id: int | None = None
    category_id: int | None = None
    subtotal_cents: int = Field(gt=0)


class CommissionPreviewOut(BaseModel):
    rule_id: int | None = None
    rule_name: str | None = None
    rate_bps: int
    fixed_fee_cents: int
    subtotal_cents: int
    commission_cents: int
    payable_to_seller_cents: int


class PayoutOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    seller_id: int
    amount_cents: int
    status: str
    reject_reason: str
    settlement_batch_id: int | None = None
    requested_by: int | None = None
    reviewed_by: int | None = None
    paid_at: datetime | None = None


class PayoutRejectRequest(BaseModel):
    reason: str = Field(default="", max_length=255)


class SettlementBatchCreate(BaseModel):
    period_start: datetime
    period_end: datetime
    note: str = Field(default="", max_length=255)


class SettlementBatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    batch_no: str
    period_start: datetime
    period_end: datetime
    status: str
    total_amount_cents: int
    seller_count: int
    payout_count: int
    note: str
    confirmed_at: datetime | None = None
    paid_at: datetime | None = None
