from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.setting import SystemSetting


async def get_setting(db: AsyncSession, category: str, tenant_id: int = 1) -> SystemSetting | None:
    result = await db.scalars(
        select(SystemSetting).where(
            SystemSetting.category == category, SystemSetting.tenant_id == tenant_id
        )
    )
    return result.first()


async def upsert_setting(
    db: AsyncSession, tenant_id: int, category: str, enabled: bool, config: dict
) -> SystemSetting:
    setting = await get_setting(db, category, tenant_id)
    if setting is None:
        setting = SystemSetting(
            tenant_id=tenant_id, category=category, enabled=enabled, config=config
        )
        db.add(setting)
    else:
        setting.enabled = enabled
        setting.config = config
    await db.flush()
    await db.refresh(setting)
    return setting
