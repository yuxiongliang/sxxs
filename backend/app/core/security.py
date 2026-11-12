import secrets
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)


def create_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def create_access_token(
    *,
    user_id: int,
    tenant_id: int | None,
    audience: str,
    roles: list[str],
    permission_version: int,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "tenant_id": tenant_id,
        "aud": audience,
        "roles": roles,
        "permission_version": permission_version,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, audience: str) -> dict:
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        audience=audience,
    )
