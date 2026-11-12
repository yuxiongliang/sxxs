"""高德 JS API 安全密钥代理（官方推荐的「代理服务器转发」方案）。

浏览器只设置 window._AMapSecurityConfig.serviceHost = {public_base_url}/_AMapService，
安全密钥由本服务注入，永远不进入前端代码。

限制：只允许 GET，且只转发到白名单里的两个上游；前缀 _AMapService 由高德 SDK 固定，
不能改名。JS API 请求本身不带租户身份，所以按请求 Host 解析租户（B6）；
Host 解析不出来时（本地开发 / 未绑定域名的租户）回落到 DEMO_TENANT_ID。
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal
from app.services import setting_resolver, tenant_domains

router = APIRouter(tags=["高德代理"])

DEMO_TENANT_ID = 1
UPSTREAM_REST = "https://restapi.amap.com"
UPSTREAM_STYLES = "https://webapi.amap.com"


async def _tenant_id_for_host(session: AsyncSession, request: Request) -> int:
    """按 Host 找租户；找不到才回落 demo —— 共用 key 只是兜底，不是常态。"""
    host = tenant_domains.normalize_request_host(request.headers.get("host"))
    tenant = await tenant_domains.tenant_by_host(session, host)
    return tenant.id if tenant is not None else DEMO_TENANT_ID


async def _security_code(request: Request) -> str:
    """代理用的 securityCode：取当前 Host 对应租户的高德配置。"""
    async with AsyncSessionLocal() as session:
        tenant_id = await _tenant_id_for_host(session, request)
        config = await setting_resolver.resolve_for_runtime(session, tenant_id, "amap")
    return str(config.get("securityCode") or "")


async def _forward(url: str, params: dict[str, str], jscode: str) -> Response:
    merged = dict(params)
    merged["jscode"] = jscode
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            upstream = await client.get(url, params=merged)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="高德代理请求失败") from exc
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/json"),
    )


@router.get("/_AMapService/v4/map/styles")
async def proxy_map_styles(request: Request):
    jscode = await _security_code(request)
    return await _forward(UPSTREAM_STYLES + "/v4/map/styles", dict(request.query_params), jscode)


@router.get("/_AMapService/{path:path}")
async def proxy_rest(request: Request, path: str):
    jscode = await _security_code(request)
    return await _forward(f"{UPSTREAM_REST}/{path.lstrip('/')}", dict(request.query_params), jscode)
