"""平台级配置接口：只接受 aud=platform 的 token。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_platform_context, require_platform_permission
from app.core.response import ok
from app.models.setting import SystemSetting
from app.models.tenant import Tenant
from app.schemas.common import ApiResponse
from app.schemas.setting import PlatformSettingUpdate, SettingOut
from app.services import platform_setting as platform_setting_service
from app.services.platform_auth import PlatformContext

router = APIRouter(prefix="/platform/settings", tags=["平台设置"])

# 白名单 2/2：分类 → 权限码。新增分类必须同时改 services/platform_setting.py。
# 注意：权限码不能在端点签名里用 `category` 推导 —— Depends(...) 的默认值在
# 函数定义时求值，那时形参还不存在，会直接 NameError。
PLATFORM_SETTING_PERMISSIONS = {
    "platform": "platform:setting:manage",
    "moderation": "platform:setting:manage",
    "payment": "platform:setting:manage",
    "sms": "platform:setting:manage",
    "email": "platform:setting:manage",
    "storage": "platform:setting:manage",
    "amap": "platform:setting:manage",
}


async def ensure_platform_setting_access(
    category: str,
    context: PlatformContext = Depends(get_platform_context),
) -> None:
    code = PLATFORM_SETTING_PERMISSIONS.get(category)
    if code is None:
        raise HTTPException(status_code=404, detail="未知的平台设置分类")
    if code not in context.permissions:
        raise HTTPException(status_code=403, detail="无权限")


@router.get(
    "/{category}",
    response_model=ApiResponse[SettingOut],
    dependencies=[Depends(ensure_platform_setting_access)],
)
async def get_platform_setting(
    category: str,
    db: AsyncSession = Depends(get_db),
):
    row = await platform_setting_service.get_platform_setting(db, category)
    return ok(SettingOut.model_validate(row))


@router.put(
    "/{category}",
    response_model=ApiResponse[SettingOut],
    dependencies=[Depends(ensure_platform_setting_access)],
)
async def save_platform_setting(
    category: str,
    payload: PlatformSettingUpdate,
    db: AsyncSession = Depends(get_db),
):
    row = await platform_setting_service.save_platform_setting(
        db, category, payload, policy_locked=payload.policy_locked
    )
    return ok(SettingOut.model_validate(row), "平台配置已保存")


@router.get(
    "/{category}/impact",
    response_model=ApiResponse[dict],
    dependencies=[Depends(require_platform_permission("platform:setting:read"))],
)
async def platform_setting_impact(category: str, db: AsyncSession = Depends(get_db)):
    """影响面：改之前得知道会影响多少租户。

    没有任何 system_settings 行的租户也算 inherit（它们会直接用平台配置）。
    """
    if category not in PLATFORM_SETTING_PERMISSIONS:
        raise HTTPException(status_code=404, detail="未知的平台设置分类")

    rows = (
        await db.execute(
            select(SystemSetting.source, func.count(SystemSetting.id))
            .where(SystemSetting.category == category)
            .group_by(SystemSetting.source)
        )
    ).all()
    counts = {str(row[0] or "inherit"): int(row[1]) for row in rows}

    tenants_total = int(
        await db.scalar(select(func.count(Tenant.id)).where(Tenant.status == "active")) or 0
    )
    override = counts.get("override", 0)
    forced = counts.get("forced_inherit", 0)
    explicit_inherit = counts.get("inherit", 0)
    # 没有行的租户默认就是 inherit
    inherit = max(explicit_inherit, tenants_total - override - forced)

    return ok(
        {
            "category": category,
            "tenants_total": tenants_total,
            "override": override,
            "inherit": inherit,
            "forced": forced,
        }
    )
