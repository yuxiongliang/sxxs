from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_platform_context
from app.core.config import settings
from app.core.response import ok
from app.schemas.auth import LoginRequest
from app.schemas.common import ApiResponse
from app.schemas.platform_auth import PlatformAuthResponse, PlatformMeResponse
from app.services import platform_auth as platform_auth_service
from app.services.platform_auth import PlatformContext

router = APIRouter(prefix="/platform/auth", tags=["平台认证"])


def _set_platform_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.platform_refresh_cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 86400,
        path="/",
    )


@router.post("/login", response_model=ApiResponse[PlatformAuthResponse])
async def platform_login(
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    result = await platform_auth_service.login(db, payload.username, payload.password)
    refresh_token = result.pop("refresh_token")
    _set_platform_refresh_cookie(response, refresh_token)
    return ok(PlatformAuthResponse.model_validate(result), "登录成功")


@router.get("/me", response_model=ApiResponse[PlatformMeResponse])
async def platform_me(context: PlatformContext = Depends(get_platform_context)):
    return ok(PlatformMeResponse.model_validate(await platform_auth_service.me(context)))


@router.post("/refresh", response_model=ApiResponse[PlatformAuthResponse])
async def platform_refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias="sxxs_platform_refresh"),
    db: AsyncSession = Depends(get_db),
):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="登录已过期")
    result = await platform_auth_service.refresh(db, refresh_token)
    new_token = result.pop("refresh_token")
    _set_platform_refresh_cookie(response, new_token)
    return ok(PlatformAuthResponse.model_validate(result), "已刷新")


@router.post("/logout", response_model=ApiResponse[None])
async def platform_logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias="sxxs_platform_refresh"),
):
    await platform_auth_service.logout(refresh_token)
    response.delete_cookie(settings.platform_refresh_cookie_name, path="/")
    return ok(None, "已退出登录")
