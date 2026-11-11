from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_context, get_db
from app.core.response import ok
from app.schemas.common import ApiResponse
from app.schemas.setting import (
    SettingOut,
    SettingTestRequest,
    SettingTestResult,
    SettingUpdate,
)
from app.services import setting as setting_service
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
    if "platform_admin" not in context.roles and code not in context.permissions:
        raise HTTPException(status_code=403, detail="无权限")


@router.get(
    "/{category}",
    response_model=ApiResponse[SettingOut],
    dependencies=[Depends(ensure_setting_access)],
)
async def get_setting(
    category: str,
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    setting = await setting_service.get_setting(db, category, context.tenant.id)
    return ok(SettingOut.model_validate(setting))


@router.put(
    "/{category}",
    response_model=ApiResponse[SettingOut],
    dependencies=[Depends(ensure_setting_access)],
)
async def save_setting(
    category: str,
    payload: SettingUpdate,
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    setting = await setting_service.save_setting(db, category, payload, context.tenant.id)
    return ok(SettingOut.model_validate(setting), "设置已保存")


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
    result = await setting_service.test_setting(
        db, category, payload.config if payload else None, context.tenant.id
    )
    return ok(result, result.message)
