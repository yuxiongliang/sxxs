"""跨域放行名单（B6）：静态开发来源 + 平台主机 + 已绑定且生效的租户域名。

为什么不能只认 .env 里的静态列表：每个租户的站点在自己的 host 上，来源域名只有运行期
才知道；写进配置意味着每加一个租户就要重启一次后端。

为什么用 60 秒缓存而不是每次查库：预检请求来自浏览器，次数不少。允许/拒绝错 60 秒
不会造成越权读取 —— 业务数据仍靠 JWT + tenant_id 过滤，最多是刚解绑的域名在缓存期内
还能发跨域请求（它拿不到 token，也就拿不到数据）。写域名时主动失效缓存，进程内立即生效。
"""

from __future__ import annotations

import time

import structlog
from sqlalchemy import select
from starlette.middleware.cors import CORSMiddleware
from starlette.types import Receive, Scope, Send

from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.models.tenant import Tenant, TenantDomain
from app.services.tenant_domains import normalize_request_host

logger = structlog.get_logger(__name__)

CACHE_TTL_SECONDS = 60.0

_active_hosts: set[str] = set()
_loaded_at: float = 0.0


def invalidate_host_cache() -> None:
    """域名增删改后调用：下一个请求重新拉库，不必等 TTL。"""
    global _loaded_at
    _loaded_at = 0.0
    _active_hosts.clear()


async def refresh_host_cache(now: float | None = None) -> None:
    """按 TTL 重新加载「允许跨域的租户 host」集合；库不可用时保持旧集合。"""
    global _loaded_at
    stamp = time.monotonic() if now is None else now
    if _loaded_at and stamp - _loaded_at < CACHE_TTL_SECONDS:
        return
    try:
        async with AsyncSessionLocal() as session:
            rows = (
                await session.execute(
                    select(TenantDomain.host)
                    .join(Tenant, Tenant.id == TenantDomain.tenant_id)
                    .where(
                        TenantDomain.status == "active",
                        Tenant.status == "active",
                    )
                )
            ).all()
    except Exception as exc:  # noqa: BLE001 - 库不可用时不能放行未知名
        logger.warning("cors_host_cache_refresh_failed", error=str(exc))
        return

    _active_hosts.clear()
    _active_hosts.update(host for (host,) in rows)
    _loaded_at = stamp


def allowed_origin(origin: str) -> bool:
    """Origin 的 host 是否属于「平台主机」或「已生效的租户域名」。"""
    host = normalize_request_host(origin.split("://", 1)[-1])
    if not host:
        return False
    if settings.platform_host and host == normalize_request_host(settings.platform_host):
        return True
    return host in _active_hosts


class TenantCORSMiddleware(CORSMiddleware):
    """在静态白名单之外，再放行已绑定且生效的租户域名。"""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            await refresh_host_cache()
        await super().__call__(scope, receive, send)

    def is_allowed_origin(self, origin: str) -> bool:
        if super().is_allowed_origin(origin=origin):
            return True
        return allowed_origin(origin)
