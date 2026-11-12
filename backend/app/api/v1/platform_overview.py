"""平台运维概览：一眼看出每个租户的配置状态。

纯聚合查询，不改变任何租户识别逻辑（Host 解析属于 B6）。
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_platform_permission
from app.core.response import ok
from app.models.setting import SystemSetting
from app.models.tenant import Tenant, TenantDomain
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/platform/overview", tags=["平台概览"])

# 默认占位值：等于这些值说明租户没真正填过（照抄了默认配置）
PLACEHOLDER_APP_IDS = {"", "2021000000000000", "wx0000000000000000"}


def _payment_configured(config: dict) -> bool:
    alipay = (config or {}).get("alipay") or {}
    wechat = (config or {}).get("wechat") or {}
    return bool(
        str(alipay.get("appId") or "") not in PLACEHOLDER_APP_IDS
        or str(wechat.get("appId") or "") not in PLACEHOLDER_APP_IDS
    )


def _domain_summary(domains: list[TenantDomain]) -> dict:
    """域名状态：B6 上线后 supported 恒为 true，具体状态看 primary_host 与计数。"""
    active = [d for d in domains if d.status == "active"]
    return {
        "supported": True,
        "primary_host": active[0].host if active else None,
        "active": len(active),
        "pending": sum(1 for d in domains if d.status == "pending"),
        "total": len(domains),
    }


@router.get("/tenants", response_model=ApiResponse[list[dict]])
async def tenant_config_overview(
    _context=Depends(require_platform_permission("platform:tenant:read")),
    db: AsyncSession = Depends(get_db),
):
    tenants = list((await db.scalars(select(Tenant).order_by(Tenant.id))).all())
    rows = list(
        (await db.scalars(select(SystemSetting).where(SystemSetting.category == "payment"))).all()
    )
    payment_by_tenant = {row.tenant_id: row for row in rows}

    domain_rows = list((await db.scalars(select(TenantDomain))).all())
    domains_by_tenant: dict[int, list[TenantDomain]] = {}
    for domain in domain_rows:
        domains_by_tenant.setdefault(domain.tenant_id, []).append(domain)

    overview = []
    for tenant in tenants:
        setting = payment_by_tenant.get(tenant.id)
        payment_config = dict(setting.config or {}) if setting else {}
        overview.append(
            {
                "tenant_id": tenant.id,
                "name": tenant.name,
                "slug": tenant.slug,
                "status": tenant.status,
                "brand": {
                    "display_name": tenant.display_name or tenant.name,
                    "customized": bool(tenant.display_name),
                    "has_logo": bool(tenant.logo_url),
                },
                "payment": {
                    "source": (setting.source if setting else "inherit"),
                    "configured": _payment_configured(payment_config),
                },
                "domain": _domain_summary(domains_by_tenant.get(tenant.id, [])),
            }
        )
    return ok(overview)
