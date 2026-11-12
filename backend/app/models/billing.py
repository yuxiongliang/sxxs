from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

# Subscription lifecycle.
SUBSCRIPTION_STATUSES = ("trialing", "active", "past_due", "cancelled")
# Invoice lifecycle.
INVOICE_STATUSES = ("pending", "paid", "void")
# Billing periods and how many days each adds to a term.
PERIOD_DAYS = {"monthly": 30, "yearly": 365}
# 非周期套餐：lifetime=永久买断，custom=管理员填的固定档期（起止日期）
NON_RECURRING_PERIODS = frozenset({"lifetime", "custom"})


class Plan(Base, TimestampMixin):
    """A SaaS plan the platform sells to tenants.

    ``quotas`` is a metric -> limit map (``None``/missing == unlimited) and
    ``features`` is a list of feature keys the plan unlocks.
    """

    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(String(255), default="")
    price_cents: Mapped[int] = mapped_column(Integer, default=0)
    period: Mapped[str] = mapped_column(String(16), default="monthly")
    # 周期套餐的时长（月）：填了它就用「月数 × 30 天」算订阅窗口；
    # lifetime / custom 不用这个字段（一个永久、一个用档期）。
    duration_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 仅 period=custom 时有值：套餐的固定档期（管理员在平台端填）
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 买断/档期套餐不允许试用（trial_days 必须为 0），由 schema 校验
    trial_days: Mapped[int] = mapped_column(Integer, default=14)
    quotas: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    features: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)


class TenantSubscription(Base, TimestampMixin):
    """One live subscription per tenant (a tenant is never double-billed)."""

    __tablename__ = "tenant_subscriptions"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_subscription_tenant"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="trialing", index=True)
    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)
    trial_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Invoice(Base, TimestampMixin):
    """A platform -> tenant bill for one billing term."""

    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    subscription_id: Mapped[int | None] = mapped_column(
        ForeignKey("tenant_subscriptions.id"), nullable=True, index=True
    )
    invoice_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(8), default="CNY")
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str] = mapped_column(String(255), default="")
