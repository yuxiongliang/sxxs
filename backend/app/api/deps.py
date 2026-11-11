from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import decode_access_token
from app.services.auth import AuthContext, context_from_payload

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    if credentials is None:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        payload = decode_access_token(credentials.credentials, audience="admin")
    except PyJWTError as exc:
        raise HTTPException(status_code=401, detail="登录已过期") from exc
    return await context_from_payload(db, payload)


def require_permission(code: str):
    async def dependency(context: AuthContext = Depends(get_current_context)) -> AuthContext:
        if "platform_admin" not in context.roles and code not in context.permissions:
            raise HTTPException(status_code=403, detail="无权限")
        return context

    return dependency


__all__ = [
    "AsyncGenerator",
    "AsyncSession",
    "get_current_context",
    "get_db",
    "require_permission",
]
