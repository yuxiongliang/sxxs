"""Seed the plan catalogue: one lifetime buyout plan.

业务口径（2026-11-12 确认）：

* 平台只卖一个「全功能 / 9999 元 / 终身 / 不抽佣」的买断套餐；
* 买断与自定义档期套餐一律 trial_days=0（不留试用、不留退款政策）；
* 历史套餐 free / pro / enterprise 置为 archived：不再对外售卖、不出现在可选列表，
  但保留行（历史订阅与账单还引用它们），其中 free 继续作为「欠费降级」的落点。

demo 租户留在 pro 上，避免演示数据被买断口径打乱；新开通的租户才走 buyout。
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import Plan
from app.models.tenant import Tenant
from app.seed_auth import DEMO_TENANT_SLUG
from app.services import billing as billing_service

BUYOUT_CODE = "buyout"

# 历史套餐：不再售卖，但必须保留这些行 —— 历史订阅/账单引用它们，
# 且 free 仍是「欠费降级」的落点、pro 仍是 demo 租户所在套餐。
ARCHIVED_PLANS = [
    {
        "code": "free",
        "name": "免费版",
        "description": "历史套餐，已下架；仅作为欠费降级落点",
        "price_cents": 0,
        "period": "monthly",
        "trial_days": 0,
        "features": ["portal"],
        "sort": 90,
    },
    {
        "code": "pro",
        "name": "专业版",
        "description": "历史套餐，已下架；demo 租户仍在用",
        "price_cents": 99000,
        "period": "monthly",
        "trial_days": 0,
        "features": ["portal", "im", "finance", "commission"],
        "sort": 91,
    },
    {
        "code": "enterprise",
        "name": "企业版",
        "description": "历史套餐，已下架",
        "price_cents": 999000,
        "period": "yearly",
        "trial_days": 0,
        "features": [
            "portal",
            "im",
            "finance",
            "commission",
            "custom-domain",
            "priority-support",
        ],
        "sort": 92,
    },
]
LEGACY_PLAN_CODES = tuple(item["code"] for item in ARCHIVED_PLANS)

SEED_PLANS = [
    {
        "code": BUYOUT_CODE,
        "name": "买断版",
        "description": "全功能、终身使用、不抽佣（一次付费买断）",
        "price_cents": 999900,
        "period": "lifetime",
        # 买断不留试用：schema 层也会拦住 trial_days>0 的组合
        "trial_days": 0,
        "features": [
            "portal",
            "im",
            "finance",
            "commission",
            "custom-domain",
            "priority-support",
        ],
        "sort": 10,
    },
]


async def seed_billing_data(db: AsyncSession) -> None:
    for item in SEED_PLANS:
        existing = (await db.scalars(select(Plan).where(Plan.code == item["code"]))).first()
        if existing is None:
            db.add(Plan(status="active", **item))
        else:
            # 已存在就对齐口径（价格、周期可改，但状态保持 active）
            existing.status = "active"
            existing.name = item["name"]
            existing.description = item["description"]
            existing.price_cents = item["price_cents"]
            existing.period = item["period"]
            existing.trial_days = item["trial_days"]
            existing.features = item["features"]
    await db.flush()

    # 历史套餐：缺了就补建（否则 demo 的 pro / 降级用的 free 会查不到），
    # 并统一标记为 archived —— 不再对外售卖，但行必须留着
    for item in ARCHIVED_PLANS:
        legacy = (await db.scalars(select(Plan).where(Plan.code == item["code"]))).first()
        if legacy is None:
            db.add(Plan(status="archived", **item))
        else:
            legacy.status = "archived"
    await db.flush()

    tenant = (await db.scalars(select(Tenant).where(Tenant.slug == DEMO_TENANT_SLUG))).first()
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
