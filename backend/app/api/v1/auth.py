from fastapi import APIRouter, Cookie, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_context, get_db
from app.core.config import settings
from app.core.response import ok
from app.schemas.auth import AuthResponse, LoginRequest, MeResponse, RegisterRequest
from app.schemas.common import ApiResponse
from app.services import auth as auth_service
from app.services import tenant_domains

router = APIRouter(prefix="/auth", tags=["认证"])


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 86400,
        path="/",
    )


@router.post("/register", response_model=ApiResponse[AuthResponse])
async def register(
    payload: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    result = await auth_service.register(
        db, payload.tenant_slug, payload.email, payload.nickname, payload.password
    )
    refresh_token = result.pop("refresh_token")
    _set_refresh_cookie(response, refresh_token)
    return ok(AuthResponse.model_validate(result), "注册成功")


@router.post("/login", response_model=ApiResponse[AuthResponse])
async def login(
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    result = await auth_service.login(db, payload.username, payload.password, payload.tenant_id)
    refresh_token = result.pop("refresh_token")
    _set_refresh_cookie(response, refresh_token)
    return ok(AuthResponse.model_validate(result), "登录成功")


@router.get("/me", response_model=ApiResponse[MeResponse])
async def me(context=Depends(get_current_context)):
    return ok(MeResponse.model_validate(await auth_service.me(context)))


@router.post("/refresh", response_model=ApiResponse[AuthResponse])
async def refresh(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias="antd_pro_refresh"),
    db: AsyncSession = Depends(get_db),
):
    if not refresh_token:
        raise auth_service.HTTPException(status_code=401, detail="登录已过期")
    # B6：refresh token 只能在它自己的站点域名下续期（Host 解析不出来时不限制）
    host_tenant = await tenant_domains.tenant_by_host(
        db, tenant_domains.normalize_request_host(request.headers.get("host"))
    )
    result = await auth_service.refresh(
        db, refresh_token, expected_tenant_id=host_tenant.id if host_tenant else None
    )
    new_token = result.pop("refresh_token")
    _set_refresh_cookie(response, new_token)
    return ok(AuthResponse.model_validate(result), "已刷新")


@router.post("/logout", response_model=ApiResponse[None])
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias="antd_pro_refresh"),
):
    await auth_service.logout(refresh_token)
    response.delete_cookie(settings.refresh_cookie_name, path="/")
    return ok(None, "已退出登录")
