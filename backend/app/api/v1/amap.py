"""高德地图：配置下发 / 测试连接 / 地理编码 / 逆地理编码 / 静态地图。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_permission
from app.core.config import settings as app_settings
from app.core.response import ok
from app.services import amap as amap_service
from app.services import setting_resolver
from app.services.auth import AuthContext

router = APIRouter(prefix="/amap", tags=["高德地图"])


async def _amap_config(db: AsyncSession, tenant_id: int) -> dict:
    """读取当前租户**生效**的高德配置（可能继承自平台）。"""
    resolved = await setting_resolver.resolve(
        db, tenant_id, "amap", mask_secrets_in_response=False
    )
    config = dict(resolved.config or {})
    config["enabled"] = bool(resolved.enabled)
    return config


def _raise_amap_error(exc: amap_service.AmapError) -> None:
    status = 400
    if exc.infocode == "MISSING_WEB_KEY":
        status = 400
    elif exc.infocode in {"10003", "10010", "10044"}:
        status = 429
    raise HTTPException(status_code=status, detail=str(exc))


@router.get("/config")
async def get_map_config(
    context: AuthContext = Depends(require_permission("amap:read")),
    db: AsyncSession = Depends(get_db),
):
    """前端渲染地图所需的最小配置（不含 webKey）。"""
    config = await _amap_config(db, context.tenant.id)
    return ok(amap_service.frontend_config(config, app_settings.public_base_url))


@router.get("/geocode")
async def geocode(
    address: str = Query(min_length=2, max_length=200),
    city: str = Query(default="", max_length=64),
    context: AuthContext = Depends(require_permission("amap:read")),
    db: AsyncSession = Depends(get_db),
):
    config = await _amap_config(db, context.tenant.id)
    try:
        result = await amap_service.geocode(config.get("webKey", ""), address, city)
    except amap_service.AmapError as exc:
        _raise_amap_error(exc)
        return ok([])
    return ok(result)


@router.get("/regeo")
async def regeo(
    lng: float = Query(ge=-180, le=180),
    lat: float = Query(ge=-90, le=90),
    extensions: str = Query(default="base", pattern="^(base|all)$"),
    context: AuthContext = Depends(require_permission("amap:read")),
    db: AsyncSession = Depends(get_db),
):
    config = await _amap_config(db, context.tenant.id)
    try:
        result = await amap_service.regeo(config.get("webKey", ""), lng, lat, extensions)
    except amap_service.AmapError as exc:
        _raise_amap_error(exc)
        return ok({})
    return ok(result)


@router.get("/static-map")
async def static_map(
    lng: float = Query(ge=-180, le=180),
    lat: float = Query(ge=-90, le=90),
    zoom: int = Query(default=12, ge=3, le=18),
    size: str = Query(default="750*300", pattern=r"^\d{2,4}\*\d{2,4}$"),
    scale: int = Query(default=1, ge=1, le=2),
    context: AuthContext = Depends(require_permission("amap:read")),
    db: AsyncSession = Depends(get_db),
):
    """服务端代理静态地图（key 不暴露给浏览器），直接回图片字节。"""
    config = await _amap_config(db, context.tenant.id)
    marker = f"mid,,A:{lng},{lat}"
    try:
        content, content_type = await amap_service.static_map(
            config.get("webKey", ""), lng, lat, zoom, size, scale, marker
        )
    except amap_service.AmapError as exc:
        _raise_amap_error(exc)
        return Response(status_code=502)
    return Response(
        content=content,
        media_type=content_type or "image/png",
        headers={"Cache-Control": "public, max-age=300"},
    )
