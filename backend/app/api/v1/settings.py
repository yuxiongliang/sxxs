"""租户设置接口。

读取一律走 `setting_resolver.resolve()`：返回的是**生效配置**（可能来自平台），
并且跟随系统时平台密钥已被脱敏。写入走 `set_source()`：只改租户自己的来源与配置。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_context, get_db
from app.core.response import ok
from app.schemas.common import ApiResponse
from app.schemas.setting import (
    SettingResolvedOut,
    SettingSourceUpdate,
    SettingTestRequest,
    SettingTestResult,
)
from app.services import setting as setting_service
from app.services import setting_resolver
from app.services.auth import AuthContext

router = APIRouter(prefix="/settings", tags=["系统设置"])

SETTING_PERMISSIONS = {
    "payment": "setting:payment",
    "sms": "setting:sms",
    "email": "setting:email",
    "storage": "setting:storage",
    "amap": "setting:amap",
}


async def ensure_setting_access(
    category: str, context: AuthContext = Depends(get_current_context)
) -> None:
    code = SETTING_PERMISSIONS.get(category)
    if code is None:
        raise HTTPException(status_code=404, detail="未知的设置分类")
    if code not in context.permissions:
        raise HTTPException(status_code=403, detail="无权限")


@router.get(
    "/{category}",
    response_model=ApiResponse[SettingResolvedOut],
    dependencies=[Depends(ensure_setting_access)],
)
async def get_setting(
    category: str,
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    resolved = await setting_resolver.resolve(db, context.tenant.id, category)
    return ok(SettingResolvedOut.model_validate(resolved, from_attributes=True))


@router.put(
    "/{category}",
    response_model=ApiResponse[SettingResolvedOut],
    dependencies=[Depends(ensure_setting_access)],
)
async def save_setting(
    category: str,
    payload: SettingSourceUpdate,
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    await setting_resolver.set_source(
        db,
        context.tenant.id,
        category,
        source=payload.source,
        enabled=payload.enabled,
        config=payload.config,
        user_id=context.user.id,
    )
    resolved = await setting_resolver.resolve(db, context.tenant.id, category)
    return ok(
        SettingResolvedOut.model_validate(resolved, from_attributes=True),
        "设置已保存",
    )


@router.post(
    "/{category}/test",
    response_model=ApiResponse[SettingTestResult],
    dependencies=[Depends(ensure_setting_access)],
)
async def test_setting(
    category: str,
    payload: SettingTestRequest | None = None,
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    # 测「生效配置」：跟随系统时测的是平台那份（服务端有真实密钥，能真测）
    config = payload.config if payload and payload.config else None
    if config is None:
        config = await setting_resolver.resolve_for_runtime(db, context.tenant.id, category)
    result = await setting_service.test_setting(db, category, config, context.tenant.id)
    return ok(result, result.message)
