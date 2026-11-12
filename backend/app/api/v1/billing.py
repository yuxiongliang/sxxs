"""Platform billing console: plans, subscriptions, invoices, usage, tenant lifecycle."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_context, get_db, require_platform_permission
from app.core.response import ok
from app.models.billing import Plan
from app.models.tenant import Tenant
from app.schemas.billing import (
    InvoiceOut,
    PlanCreate,
    PlanOut,
    PlanUpdate,
    RenewRequest,
    SubscribeRequest,
    SubscriptionOut,
    TenantStatusRequest,
    TenantUpdateRequest,
)
from app.schemas.common import ApiResponse
from app.services import audit as audit_service
from app.services import billing as billing_service
from app.services import platform as platform_service
from app.services.auth import AuthContext

router = APIRouter(prefix="/platform", tags=["平台计费"])

READ = "platform:tenant:read"
MANAGE = "platform:tenant:manage"


async def _get_tenant(db: AsyncSession, tenant_id: int) -> Tenant:
    tenant = await db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="租户不存在")
    return tenant


# --------------------------------------------------------------------------- #
# Plans
# --------------------------------------------------------------------------- #


@router.get("/plans", response_model=ApiResponse[list[PlanOut]])
async def list_plans(
    include_archived: bool = Query(default=False),
    _context=Depends(require_platform_permission(READ)),
    db: AsyncSession = Depends(get_db),
):
    plans = await billing_service.list_plans(db, include_archived)
    return ok([PlanOut.model_validate(plan) for plan in plans])


@router.post("/plans", response_model=ApiResponse[PlanOut])
async def create_plan(
    payload: PlanCreate,
    _context=Depends(require_platform_permission(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    if await billing_service.get_plan_by_code(db, payload.code) is not None:
        raise HTTPException(status_code=409, detail="套餐编码已存在")
    plan = Plan(
        code=payload.code,
        name=payload.name,
        description=payload.description,
        price_cents=payload.price_cents,
        period=payload.period,
        trial_days=payload.trial_days,
        quotas=payload.quotas,
        features=payload.features or [],
        sort=payload.sort,
        status=payload.status,
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return ok(PlanOut.model_validate(plan), "套餐已创建")


@router.put("/plans/{plan_id}", response_model=ApiResponse[PlanOut])
async def update_plan(
    plan_id: int,
    payload: PlanUpdate,
    _context=Depends(require_platform_permission(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    plan = await db.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="套餐不存在")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(plan, key, value)
    await db.commit()
    await db.refresh(plan)
    return ok(PlanOut.model_validate(plan), "套餐已更新")


# --------------------------------------------------------------------------- #
# Subscriptions
# --------------------------------------------------------------------------- #


@router.get("/tenants/{tenant_id}/subscription", response_model=ApiResponse[dict])
async def get_tenant_subscription(
    tenant_id: int,
    _context=Depends(require_platform_permission(READ)),
    db: AsyncSession = Depends(get_db),
):
    await _get_tenant(db, tenant_id)
    return ok(await billing_service.usage_report(db, tenant_id))


@router.post("/tenants/{tenant_id}/subscription", response_model=ApiResponse[SubscriptionOut])
async def subscribe_tenant(
    tenant_id: int,
    payload: SubscribeRequest,
    _context=Depends(require_platform_permission(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    await _get_tenant(db, tenant_id)
    subscription = await billing_service.start_subscription(
        db, tenant_id, payload.plan_id, trial=payload.trial
    )
    if subscription is None:
        raise HTTPException(status_code=400, detail="套餐目录为空，请先创建套餐")
    return ok(SubscriptionOut.model_validate(subscription), "订阅已生效")


@router.post("/tenants/{tenant_id}/renew", response_model=ApiResponse[dict])
async def renew_tenant(
    tenant_id: int,
    payload: RenewRequest,
    _context=Depends(require_platform_permission(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    await _get_tenant(db, tenant_id)
    subscription, invoice = await billing_service.renew_subscription(db, tenant_id, payload.days)
    return ok(
        {
            "subscription": SubscriptionOut.model_validate(subscription).model_dump(mode="json"),
            "invoice": InvoiceOut.model_validate(invoice).model_dump(mode="json")
            if invoice
            else None,
        },
        "续费成功，已生成账单",
    )


@router.get("/tenants/{tenant_id}/usage", response_model=ApiResponse[dict])
async def tenant_usage(
    tenant_id: int,
    _context=Depends(require_platform_permission(READ)),
    db: AsyncSession = Depends(get_db),
):
    await _get_tenant(db, tenant_id)
    return ok(await billing_service.usage_report(db, tenant_id))


# --------------------------------------------------------------------------- #
# Tenant lifecycle: edit / suspend / resume
# --------------------------------------------------------------------------- #


@router.put("/tenants/{tenant_id}", response_model=ApiResponse[dict])
async def update_tenant(
    tenant_id: int,
    payload: TenantUpdateRequest,
    _context=Depends(require_platform_permission(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    tenant = await _get_tenant(db, tenant_id)
    if tenant.slug == "demo" and payload.status == "suspended":
        raise HTTPException(status_code=400, detail="演示租户不允许停用")
    before = {"name": tenant.name, "status": tenant.status}
    for key, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(tenant, key, value)
    await audit_service.record(
        db,
        action=audit_service.ACTION_TENANT_UPDATED,
        tenant_id=tenant.id,
        actor_id=_context.user.id,
        target_type="tenant",
        target_id=tenant.id,
        before=before,
        after={"name": tenant.name, "status": tenant.status},
    )
    await db.commit()
    await db.refresh(tenant)
    return ok(
        {"id": tenant.id, "name": tenant.name, "slug": tenant.slug, "status": tenant.status},
        "租户已更新",
    )


@router.post("/tenants/{tenant_id}/suspend", response_model=ApiResponse[dict])
async def suspend_tenant(
    tenant_id: int,
    payload: TenantStatusRequest,
    _context=Depends(require_platform_permission(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    tenant = await _get_tenant(db, tenant_id)
    if tenant.slug == "demo":
        raise HTTPException(status_code=400, detail="演示租户不允许停用")
    tenant.status = "suspended"
    await audit_service.record(
        db,
        action=audit_service.ACTION_TENANT_SUSPENDED,
        tenant_id=tenant.id,
        actor_id=_context.user.id,
        target_type="tenant",
        target_id=tenant.id,
        before={"status": "active"},
        after={"status": "suspended", "reason": payload.reason},
    )
    await db.commit()
    await db.refresh(tenant)
    return ok(
        {"id": tenant.id, "status": tenant.status, "reason": payload.reason},
        "租户已停用，所有 API 将返回 403",
    )


@router.post("/tenants/{tenant_id}/resume", response_model=ApiResponse[dict])
async def resume_tenant(
    tenant_id: int,
    _context=Depends(require_platform_permission(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    tenant = await _get_tenant(db, tenant_id)
    tenant.status = "active"
    await audit_service.record(
        db,
        action=audit_service.ACTION_TENANT_RESUMED,
        tenant_id=tenant.id,
        actor_id=_context.user.id,
        target_type="tenant",
        target_id=tenant.id,
        before={"status": "suspended"},
        after={"status": "active"},
    )
    await db.commit()
    await db.refresh(tenant)
    return ok({"id": tenant.id, "status": tenant.status}, "租户已恢复")


# --------------------------------------------------------------------------- #
# Invoices
# --------------------------------------------------------------------------- #


@router.get("/invoices", response_model=ApiResponse[list[InvoiceOut]])
async def list_invoices(
    tenant_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    _context=Depends(require_platform_permission(READ)),
    db: AsyncSession = Depends(get_db),
):
    invoices = await billing_service.list_invoices(db, tenant_id, status)
    return ok([InvoiceOut.model_validate(item) for item in invoices])


@router.post("/invoices/{invoice_id}/pay", response_model=ApiResponse[InvoiceOut])
async def pay_invoice(
    invoice_id: int,
    _context=Depends(require_platform_permission(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    invoice = await billing_service.pay_invoice(db, invoice_id)
    return ok(InvoiceOut.model_validate(invoice), "账单已支付")


@router.post("/billing/run-cycle", response_model=ApiResponse[dict])
async def run_billing_cycle(
    _context=Depends(require_platform_permission(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """Run the recurring billing cycle now (renewals, invoices, dunning).

    The same code path runs on a timer inside the app; this endpoint exists so
    operations can re-run it (or an external CronJob can drive it when
    BILLING_SCHEDULER_ENABLED is false).
    """
    summary = await billing_service.run_billing_cycle(db)
    return ok(summary, "账单巡检完成")


@router.get("/tenants-list", response_model=ApiResponse[list[dict]])
async def list_tenants_with_plan(
    _context=Depends(require_platform_permission(READ)),
    db: AsyncSession = Depends(get_db),
):
    """Tenant list enriched with plan / subscription / usage for the console."""
    tenants = await platform_service.list_tenants(db)
    result = []
    for tenant in tenants:
        report = await billing_service.usage_report(db, tenant.id)
        result.append(
            {
                "id": tenant.id,
                "name": tenant.name,
                "slug": tenant.slug,
                "status": tenant.status,
                "created_at": tenant.created_at,
                "plan": report["plan"],
                "subscription": report["subscription"],
                "used": report["used"],
                "quotas": report["quotas"],
                "exceeded": report["exceeded"],
                "days_left": report["days_left"],
            }
        )
    return ok(result)


# --------------------------------------------------------------------------- #
# Tenant-facing view (any member of the tenant)
# --------------------------------------------------------------------------- #

tenant_router = APIRouter(prefix="/tenant", tags=["租户订阅"])


@tenant_router.get("/subscription", response_model=ApiResponse[dict])
async def my_subscription(
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    """Current plan, quotas, usage and remaining days for the caller's tenant."""
    return ok(await billing_service.usage_report(db, context.tenant.id))
