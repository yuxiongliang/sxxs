from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

# Commission is expressed in basis points: 1000 bps == 10%.
DEFAULT_COMMISSION_BPS = 1000
# Payout lifecycle: request -> review -> disbursement.
PAYOUT_STATUSES = ("pending", "approved", "rejected", "paid")
# Settlement batch lifecycle.
BATCH_STATUSES = ("draft", "confirmed", "paid")


class CommissionRule(Base, TimestampMixin):
    """A configurable commission rule.

    Resolution order (most specific win, then highest ``priority``, then newest):
    seller + category > seller > category > tenant default (both NULL).
    ``effective_from`` / ``effective_to`` bound the rule to an accounting period.
    """

    __tablename__ = "commission_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(
        String(64), default="默认佣金规则", server_default="默认佣金规则"
    )
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    seller_id: Mapped[int | None] = mapped_column(ForeignKey("sellers.id"), nullable=True)
    rate_bps: Mapped[int] = mapped_column(Integer, default=DEFAULT_COMMISSION_BPS)
    fixed_fee_cents: Mapped[int] = mapped_column(Integer, default=0)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_ledger_idempotency"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id"), index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    seller_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("seller_orders.id"), nullable=True
    )
    # sale / commission / refund / refund_commission / payout
    type: Mapped[str] = mapped_column(String(32))
    amount_cents: Mapped[int] = mapped_column(Integer)
    idempotency_key: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Payout(Base, TimestampMixin):
    """A seller withdrawal request and its review trail.

    ``pending`` -> reviewed -> ``approved`` / ``rejected`` -> ``paid``.
    Only ``approved`` payouts can be swept into a settlement batch.
    """

    __tablename__ = "payouts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id"), index=True)
    amount_cents: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    requested_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reject_reason: Mapped[str] = mapped_column(String(255), default="", server_default="")
    settlement_batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("settlement_batches.id"), nullable=True, index=True
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SettlementBatch(Base, TimestampMixin):
    """A payout run covering an accounting period (账期)."""

    __tablename__ = "settlement_batches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    batch_no: Mapped[str] = mapped_column(String(64), index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    total_amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    seller_count: Mapped[int] = mapped_column(Integer, default=0)
    payout_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str] = mapped_column(String(255), default="")
