from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

# 非周期套餐：永久买断 / 管理员自定义档期；这两类一律不许试用
NON_RECURRING_PERIODS = frozenset({'lifetime', 'custom'})
PERIOD_PATTERN = '^(monthly|yearly|lifetime|custom)$'


class PlanCreate(BaseModel):
    code: str = Field(min_length=2, max_length=32, pattern="^[a-z0-9-]+$")
    name: str = Field(min_length=1, max_length=64)
    description: str = Field(default="", max_length=255)
    price_cents: int = Field(default=0, ge=0)
    period: str = Field(default="monthly", pattern=PERIOD_PATTERN)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    trial_days: int = Field(default=14, ge=0, le=365)
    quotas: dict[str, int | None] | None = None
    features: list[str] | None = None
    sort: int = Field(default=0, ge=0)
    status: str = Field(default="active", pattern="^(active|archived)$")

    @model_validator(mode="after")
    def _check_term(self):
        if self.period in NON_RECURRING_PERIODS and self.trial_days:
            raise ValueError("永久买断/自定义档期套餐不能设置试用天数")
        if self.period == "custom":
            if self.starts_at is None or self.ends_at is None:
                raise ValueError("自定义档期必须同时给开始时间和到期时间")
            if self.ends_at <= self.starts_at:
                raise ValueError("到期时间必须晚于开始时间")
        return self


class PlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=255)
    price_cents: int | None = Field(default=None, ge=0)
    period: str | None = Field(default=None, pattern=PERIOD_PATTERN)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    trial_days: int | None = Field(default=None, ge=0, le=365)
    quotas: dict[str, int | None] | None = None
    features: list[str] | None = None
    sort: int | None = Field(default=None, ge=0)
    status: str | None = Field(default=None, pattern="^(active|archived)$")


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    description: str
    price_cents: int
    period: str
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    trial_days: int
    quotas: dict[str, int | None] | None = None
    features: list[str] | None = None
    status: str
    sort: int


class SubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    plan_id: int
    status: str
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    trial_end: datetime | None = None


class SubscribeRequest(BaseModel):
    plan_id: int
    trial: bool = False


class RenewRequest(BaseModel):
    days: int | None = Field(default=None, ge=1, le=730)


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    subscription_id: int | None = None
    invoice_no: str
    amount_cents: int
    currency: str
    status: str
    period_start: datetime
    period_end: datetime
    due_at: datetime | None = None
    paid_at: datetime | None = None
    note: str


class TenantUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    status: str | None = Field(default=None, pattern="^(active|suspended)$")


class TenantStatusRequest(BaseModel):
    reason: str = Field(default="", max_length=255)
