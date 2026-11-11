"""Seed the plan catalogue and put the demo tenant on a comfortable plan.

The demo tenant is placed on ``pro`` so that quota enforcement never blocks the
seeded demo data or the test suite; new tenants created through the platform API
start on ``free`` with a trial window.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import Plan
from app.models.tenant import Tenant
from app.seed_auth import DEMO_TENANT_SLUG
from app.services import billing as billing_service

SEED_PLANS = [
    {
        "code": "free",
        "name": "免费版",
        "description": "试用市场，适合验证流程",
        "price_cents": 0,
        "period": "monthly",
        "trial_days": 14,
        "quotas": {"products": 50, "members": 5},
        "features": ["portal"],
        "sort": 10,
    },
    {
        "code": "pro",
        "name": "专业版",
        "description": "完整 C2C 能力，含 IM 与财务中心",
        "price_cents": 99000,
        "period": "monthly",
        "trial_days": 14,
        "quotas": {"products": 5000, "members": 50},
        "features": ["portal", "im", "finance", "commission"],
        "sort": 20,
    },
    {
        "code": "enterprise",
        "name": "企业版",
        "description": "不限商品与成员，独立结算",
        "price_cents": 999000,
        "period": "yearly",
        "trial_days": 30,
        "quotas": {"products": None, "members": None},
        "features": ["portal", "im", "finance", "commission", "custom-domain", "priority-support"],
        "sort": 30,
    },
]


async def seed_billing_data(db: AsyncSession) -> None:
    for item in SEED_PLANS:
        existing = (
            await db.scalars(select(Plan).where(Plan.code == item["code"]))
        ).first()
        if existing is None:
            db.add(Plan(status="active", **item))
    await db.flush()

    tenant = (
        await db.scalars(select(Tenant).where(Tenant.slug == DEMO_TENANT_SLUG))
    ).first()
    if tenant is None:
        await db.commit()
        return

    subscription = await billing_service.get_subscription(db, tenant.id)
    if subscription is None:
        pro = (await db.scalars(select(Plan).where(Plan.code == "pro"))).first()
        await billing_service.start_subscription(
            db, tenant.id, pro.id if pro else None, trial=False, commit=False
        )

    await db.commit()
