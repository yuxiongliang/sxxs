"""平台级配置（无 tenant_id）。租户级配置仍走 `app.services.setting`。"""

import copy

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform_setting import PlatformSetting
from app.schemas.setting import SettingUpdate
from app.services.setting import DEFAULT_SETTINGS as TENANT_SETTING_DEFAULTS

# 白名单 1/2：允许的分类（api/v1/platform_settings.py 里还有一层权限白名单）
# 白名单 1/2：允许的分类（api/v1/platform_settings.py 里还有一层权限白名单）
ALLOWED_CATEGORIES = {
    "platform",
    "moderation",
    "payment",
    "sms",
    "email",
    "storage",
    "amap",
}

DEFAULT_PLATFORM_SETTINGS_MODERATION = {
    "enabled": True,
    "config": {
        "provider": "null",
        "endpoint": "",
        "apiKey": "",
        "timeoutMs": 5000,
        "maxSendBytes": 8 * 1024 * 1024,
        "dailyQuota": 500,
        "autoApproveOnNull": True,
        "failMode": {"default": "manual", "kyc": "closed", "im": "open"},
    },
}


DEFAULT_PLATFORM_SETTINGS: dict[str, dict] = {
    "platform": {
        "enabled": True,
        "config": {
            "name": "赛霄玄思 SaaS 管理平台",
            "shortName": "赛霄玄思",
            "contactEmail": "",
            "supportUrl": "",
            "registrationOpen": True,
            "defaultTrialDays": 14,
            "announcement": "",
        },
    },
}


def _ensure_category(category: str) -> None:
    if category not in ALLOWED_CATEGORIES:
        raise HTTPException(status_code=404, detail="未知的平台设置分类")


async def _get_row(db: AsyncSession, category: str) -> PlatformSetting | None:
    return (
        await db.scalars(select(PlatformSetting).where(PlatformSetting.category == category))
    ).first()


async def get_platform_setting(db: AsyncSession, category: str) -> PlatformSetting:
    _ensure_category(category)
    row = await _get_row(db, category)
    if row is None:
        default = DEFAULT_PLATFORM_SETTINGS[category]
        row = PlatformSetting(
            category=category,
            enabled=default["enabled"],
            config=copy.deepcopy(default["config"]),
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return row


async def save_platform_setting(
    db: AsyncSession,
    category: str,
    payload: SettingUpdate,
    *,
    policy_locked: bool | None = None,
) -> PlatformSetting:
    _ensure_category(category)
    row = await _get_row(db, category)
    if row is None:
        row = PlatformSetting(category=category)
        db.add(row)
    row.enabled = payload.enabled
    row.config = payload.config
    if policy_locked is not None:
        row.policy_locked = policy_locked
    # 版本 +1：供缓存键与「配置是否变更」判断
    row.version = (row.version or 0) + 1
    await db.commit()
    await db.refresh(row)
    return row


DEFAULT_PLATFORM_SETTINGS["moderation"] = DEFAULT_PLATFORM_SETTINGS_MODERATION

# 5 类「可被租户继承」的平台配置。
# enabled=False 表示平台尚未真正接管该类配置：租户切到 inherit 时会自动回落
# 自己的历史配置（见 services/setting_resolver.py 的优先级 3），
# 因此「存量租户改 inherit」不会让全站支付/邮件在平台没配好之前就不可用。
DEFAULT_PLATFORM_SETTINGS.update(
    {
        category: {
            "enabled": False,
            "config": copy.deepcopy(TENANT_SETTING_DEFAULTS[category]["config"]),
        }
        for category in ("payment", "sms", "email", "storage", "amap")
    }
)
