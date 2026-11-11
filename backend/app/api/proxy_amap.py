"""高德 JS API 安全密钥代理（官方推荐的「代理服务器转发」方案）。

浏览器只设置 window._AMapSecurityConfig.serviceHost = {public_base_url}/_AMapService，
安全密钥由本服务注入，永远不进入前端代码。

限制：只允许 GET，且只转发到白名单里的两个上游；前缀 _AMapService 由高德 SDK 固定，
不能改名。因为 JS API 请求不带租户身份，这里固定使用 DEMO_TENANT_ID 的配置 ——
多租户场景若要各自使用自己的 key，需要按域名/子域映射租户后再取配置。
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Request, Response

from app.core.db import AsyncSessionLocal
from app.services import setting as setting_service

router = APIRouter(tags=["高德代理"])

DEMO_TENANT_ID = 1
UPSTREAM_REST = "https://restapi.amap.com"
UPSTREAM_STYLES = "https://webapi.amap.com"


async def _security_code() -> str:
    async with AsyncSessionLocal() as session:
        setting = await setting_service.get_setting(session, "amap", DEMO_TENANT_ID)
        config = setting.config or {}
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
    jscode = await _security_code()
    return await _forward(UPSTREAM_STYLES + "/v4/map/styles", dict(request.query_params), jscode)


@router.get("/_AMapService/{path:path}")
async def proxy_rest(request: Request, path: str):
    jscode = await _security_code()
    return await _forward(f"{UPSTREAM_REST}/{path.lstrip('/')}", dict(request.query_params), jscode)
