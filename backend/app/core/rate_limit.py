"""Redis-backed request rate limiting.

Plan §11 lists "接口限流" as a P0 item before exposure. The limiter is a fixed
window counter keyed by client IP + scope:

* ``rl:global:{ip}:{window}``      -> ordinary API traffic
* ``rl:auth:{ip}:{window}``        -> login / register / refresh (much stricter)

Behaviour:

* ``429`` with a ``Retry-After`` header once the budget is exhausted.
* Redis failures **fail open** (a cache outage must not lock every user out) but
  are logged, so the metric still shows the gap.
* ``/health``, ``/docs``, ``/openapi.json`` and static uploads are never limited.
"""

from __future__ import annotations

import time

import structlog
from fastapi import Request
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.config import settings
from app.core.redis import redis_client

logger = structlog.get_logger(__name__)

AUTH_PATHS = (
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
)

EXEMPT_PREFIXES = (
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/uploads",
)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _should_limit(path: str) -> bool:
    return not path.startswith(EXEMPT_PREFIXES)


def _limit_for(path: str) -> tuple[str, int, int]:
    """Return (scope, max_requests, window_seconds) for a path."""
    if path.startswith(AUTH_PATHS):
        return "auth", settings.rate_limit_auth_requests, settings.rate_limit_auth_window_seconds
    return "global", settings.rate_limit_requests, settings.rate_limit_window_seconds


async def _hit(key: str, window: int) -> int:
    """Increment the counter for the current window and return its value."""
    bucket = int(time.time()) // window
    redis_key = f"{key}:{bucket}"
    value = await redis_client.incr(redis_key)
    if value == 1:
        await redis_client.expire(redis_key, window)
    return int(value)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not settings.rate_limit_enabled:
            return await call_next(request)

        path = request.url.path
        if not _should_limit(path):
            return await call_next(request)

        scope, limit, window = _limit_for(path)
        if limit <= 0:
            return await call_next(request)

        key = f"rl:{scope}:{_client_ip(request)}"
        try:
            hits = await _hit(key, window)
        except RedisError as exc:
            logger.warning("rate_limit_unavailable", error=str(exc), scope=scope)
            return await call_next(request)

        if hits > limit:
            retry_after = window
            logger.info("rate_limited", scope=scope, path=path, hits=hits, limit=limit)
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(retry_after)},
                content={
                    "code": 429,
                    "message": "请求过于频繁，请稍后再试",
                    "data": {"scope": scope, "limit": limit, "window_seconds": window},
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - hits))
        return response
