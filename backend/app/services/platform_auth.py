"""平台（赛霄玄思 SaaS 管理平台）认证，与租户认证彻底隔离。

隔离手段：
1. 平台 token 的 `aud` 是 `platform`；租户接口只接受 `aud=admin`，两边互不兼容。
2. 平台账号不绑定租户，身份由 `users.is_platform_admin` 单独标识。
3. refresh token 在 Redis 里带 `scope=platform`：平台 refresh 换不出租户 token，
   租户 refresh 也无法在平台端换新 token。
"""

import json
from dataclasses import dataclass

import structlog
from fastapi import HTTPException
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import redis_client
from app.core.security import create_access_token, create_refresh_token, verify_password
from app.dao import user as user_dao
from app.models.permission import Permission
from app.models.user import User

logger = structlog.get_logger(__name__)

PLATFORM_AUDIENCE = "platform"
PLATFORM_ROLE = "platform_admin"
PLATFORM_PERMISSION_PREFIX = "platform:"


@dataclass
class PlatformContext:
    db: AsyncSession
    user: User
    roles: list[str]
    permissions: list[str]
    permission_version: int


def _platform_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "nickname": user.nickname,
        "email": user.email,
        "avatar": None,
    }


async def _platform_permissions(db: AsyncSession) -> list[str]:
    rows = (await db.execute(select(Permission.code).order_by(Permission.code))).all()
    return [str(row[0]) for row in rows if str(row[0]).startswith(PLATFORM_PERMISSION_PREFIX)]


async def build_platform_context(db: AsyncSession, user: User) -> PlatformContext:
    if user.status != "active":
        raise HTTPException(status_code=403, detail="用户已停用")
    if not user.is_platform_admin:
        raise HTTPException(status_code=403, detail="该账号不是平台管理员")
    return PlatformContext(
        db=db,
        user=user,
        roles=[PLATFORM_ROLE],
        permissions=await _platform_permissions(db),
        permission_version=0,
    )


async def platform_context_from_payload(db: AsyncSession, payload: dict) -> PlatformContext:
    try:
        user_id = int(payload.get("sub", 0))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="登录凭证无效") from exc
    if payload.get("tenant_id") not in (None, "", 0):
        # 平台 token 不允许携带租户上下文
        raise HTTPException(status_code=401, detail="登录凭证无效")
    user = await user_dao.get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    return await build_platform_context(db, user)


async def _issue_tokens(context: PlatformContext) -> tuple[str, str]:
    access_token = create_access_token(
        user_id=context.user.id,
        tenant_id=None,
        audience=PLATFORM_AUDIENCE,
        roles=context.roles,
        permission_version=context.permission_version,
    )
    refresh_token = create_refresh_token()
    try:
        await redis_client.setex(
            f"refresh:{refresh_token}",
            settings.refresh_token_expire_days * 86400,
            json.dumps({"user_id": context.user.id, "scope": "platform"}),
        )
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="会话服务不可用") from exc
    return access_token, refresh_token


async def _response(context: PlatformContext) -> dict:
    access_token, refresh_token = await _issue_tokens(context)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
        "user": _platform_user(context.user),
        "roles": context.roles,
        "permissions": context.permissions,
        "permission_version": context.permission_version,
    }


async def login(db: AsyncSession, username: str, password: str) -> dict:
    user = await user_dao.get_by_username(db, username)
    if user is None or not user.password_hash or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return await _response(await build_platform_context(db, user))


async def me(context: PlatformContext) -> dict:
    return {
        "user": _platform_user(context.user),
        "roles": context.roles,
        "permissions": context.permissions,
        "permission_version": context.permission_version,
    }


async def refresh(db: AsyncSession, refresh_token: str) -> dict:
    try:
        raw = await redis_client.get(f"refresh:{refresh_token}")
    except Exception as exc:
        raise HTTPException(status_code=503, detail="会话服务不可用") from exc
    if not raw:
        raise HTTPException(status_code=401, detail="登录已过期")
    try:
        data = json.loads(raw)
        if data.get("scope") != "platform":
            raise KeyError("scope")
        user_id = int(data["user_id"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="登录已过期") from exc
    user = await user_dao.get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="登录已过期")
    context = await build_platform_context(db, user)
    try:
        await redis_client.delete(f"refresh:{refresh_token}")
    except RedisError as exc:
        logger.warning("platform_refresh_token_delete_failed", error=str(exc))
    return await _response(context)


async def logout(refresh_token: str | None) -> None:
    if not refresh_token:
        return
    try:
        await redis_client.delete(f"refresh:{refresh_token}")
    except RedisError as exc:
        logger.warning("platform_logout_failed", error=str(exc))
