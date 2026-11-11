"""高德地图（AMap）接入：Web 服务 REST + 前端 JS API 配置下发。

安全边界（重要）：

* 只使用 **Web 服务 key** 调 REST，key 只存在后端，浏览器永远拿不到。
* JS API 的 key 与安全密钥（securityJsCode）单独存；安全密钥默认**不走明文**，
  而是通过本服务的 /_AMapService 反向代理注入（官方推荐做法，见 docs）。
* 高德响应封套为 {status, info, infocode} 且 status 是**字符串**，HTTP 恒为 200，
  因此绝不能用 HTTP 状态码判成败。
"""

from __future__ import annotations

from typing import Any

import httpx

REST_BASE = "https://restapi.amap.com"
# 安全密钥代理允许转发的目标（白名单，避免变成开放代理）
JS_STYLE_HOST = "https://webapi.amap.com"

# 高频错误码 -> 中文可读说明。10009 是最常见的坑：key 与平台不符。
ERROR_HINTS: dict[str, str] = {
    "10001": "key 无效（INVALID_USER_KEY）",
    "10002": "服务暂不可用",
    "10003": "当日配额已用尽",
    "10005": "IP 白名单校验失败",
    "10006": "域名白名单校验失败（JS API key 需要配置域名）",
    "10008": "安全密钥不正确或未设置",
    "10009": "key 与绑定平台不符（JS API key 不能调 Web 服务，反之亦然）",
    "10010": "单 IP 访问超限",
    "10012": "该 key 无此服务权限",
    "10013": "key 已被删除",
    "10016": "高德服务繁忙，请稍后重试",
    "10044": "账号维度日调用量超限",
}


class AmapError(Exception):
    """高德返回 status != "1" 时抛出，携带 infocode 便于定位。"""

    def __init__(self, info: str, infocode: str, scope: str = "") -> None:
        self.info = info or "UNKNOWN"
        self.infocode = infocode or ""
        self.scope = scope
        hint = ERROR_HINTS.get(self.infocode, self.info)
        super().__init__(f"高德接口失败：{hint}（infocode={self.infocode or '-'}）")


def _s(value: Any) -> str:
    """高德有时把空值返回成 []，统一收敛成字符串。"""
    if value is None:
        return ""
    if isinstance(value, list):
        return ""
    return str(value)


async def _call(web_key: str, path: str, params: dict[str, Any], scope: str) -> dict[str, Any]:
    if not web_key:
        raise AmapError("MISSING_WEB_KEY", "MISSING_WEB_KEY", scope)
    query = {key: value for key, value in params.items() if value not in (None, "")}
    query["key"] = web_key
    try:
        async with httpx.AsyncClient(base_url=REST_BASE, timeout=10) as client:
            response = await client.get(path, params=query)
    except httpx.HTTPError as exc:  # 网络层失败与业务失败要分开报
        raise AmapError(f"NETWORK_ERROR: {exc}", "NETWORK_ERROR", scope) from exc
    try:
        payload = response.json()
    except ValueError as exc:
        raise AmapError("INVALID_RESPONSE", "INVALID_RESPONSE", scope) from exc
    if str(payload.get("status")) != "1":
        raise AmapError(_s(payload.get("info")), _s(payload.get("infocode")), scope)
    return payload


async def geocode(web_key: str, address: str, city: str = "") -> list[dict[str, Any]]:
    """地址 -> 坐标（经纬度）。返回简化后的候选列表。"""
    payload = await _call(web_key, "/v3/geocode/geo", {"address": address, "city": city}, "geocode")
    items = payload.get("geocodes") or []
    return [
        {
            "formatted_address": _s(item.get("formatted_address")),
            "location": _s(item.get("location")),
            "province": _s(item.get("province")),
            "city": _s(item.get("city")),
            "district": _s(item.get("district")),
            "adcode": _s(item.get("adcode")),
            "level": _s(item.get("level")),
        }
        for item in items
        if isinstance(item, dict)
    ]


async def regeo(
    web_key: str, longitude: float, latitude: float, extensions: str = "base"
) -> dict[str, Any]:
    """坐标 -> 地址。注意高德是「经度,纬度」。"""
    payload = await _call(
        web_key,
        "/v3/geocode/regeo",
        {"location": f"{longitude},{latitude}", "extensions": extensions},
        "regeo",
    )
    result = payload.get("regeocode") or {}
    component = result.get("addressComponent") or {}
    pois = result.get("pois") or []
    return {
        "formatted_address": _s(result.get("formatted_address")),
        "province": _s(component.get("province")),
        "city": _s(component.get("city")) or _s(component.get("province")),
        "district": _s(component.get("district")),
        "township": _s(component.get("township")),
        "street": _s(
            component.get("streetNumber", {}).get("street")
            if isinstance(component.get("streetNumber"), dict)
            else ""
        ),
        "adcode": _s(component.get("adcode")),
        "pois": [
            {"name": _s(item.get("name")), "location": _s(item.get("location"))}
            for item in (pois or [])[:10]
            if isinstance(item, dict)
        ]
        if extensions == "all"
        else [],
    }


async def static_map(
    web_key: str,
    longitude: float,
    latitude: float,
    zoom: int = 12,
    size: str = "750*300",
    scale: int = 1,
    markers: str = "",
) -> tuple[bytes, str]:
    """服务端直接取一张静态地图 PNG。失败时抛 AmapError（高德会返回 JSON 错误）。"""
    if not web_key:
        raise AmapError("MISSING_WEB_KEY", "MISSING_WEB_KEY", "staticmap")
    params = {
        "location": f"{longitude},{latitude}",
        "zoom": zoom,
        "size": size,
        "scale": scale,
        "key": web_key,
    }
    if markers:
        params["markers"] = markers
    try:
        async with httpx.AsyncClient(base_url=REST_BASE, timeout=15) as client:
            response = await client.get("/v3/staticmap", params=params)
    except httpx.HTTPError as exc:
        raise AmapError(f"NETWORK_ERROR: {exc}", "NETWORK_ERROR", "staticmap") from exc
    content_type = response.headers.get("content-type", "")
    if content_type.startswith("image/"):
        return response.content, content_type
    try:
        payload = response.json()
    except ValueError:
        raise AmapError("INVALID_RESPONSE", "INVALID_RESPONSE", "staticmap") from None
    raise AmapError(_s(payload.get("info")), _s(payload.get("infocode")), "staticmap")


# --------------------------------------------------------------------------- #
# 请求解析（供 API 层复用）
# --------------------------------------------------------------------------- #


def parse_location(raw: str) -> tuple[float, float]:
    """把 "经度,纬度" 解析成 (lng, lat)。高德是经度在前，别写反。"""
    parts = [item.strip() for item in (raw or "").split(",")]
    if len(parts) != 2:
        raise ValueError("坐标格式应为 经度,纬度")
    lng = float(parts[0])
    lat = float(parts[1])
    if not (-180 <= lng <= 180 and -90 <= lat <= 90):
        raise ValueError("坐标超出合法范围")
    return lng, lat


def build_service_host(public_base_url: str) -> str:
    """前端 _AMapSecurityConfig.serviceHost 的取值。"""
    return public_base_url.rstrip("/") + "/_AMapService"


def frontend_config(config: dict[str, Any], public_base_url: str) -> dict[str, Any]:
    """下发给浏览器的地图配置。**不含 webKey**。

    安全密钥默认不下发明文：走 /_AMapService 代理，浏览器只拿到 serviceHost。
    只有显式关闭 useProxy 时才回退到明文方式（官方标注不建议生产使用）。
    """
    use_proxy = bool(config.get("useProxy", True))
    payload: dict[str, Any] = {
        "enabled": bool(config.get("enabled", True)),
        "jsKey": config.get("jsKey", ""),
        "defaultCenter": config.get("defaultCenter", "116.397428,39.90923"),
        "defaultZoom": int(config.get("defaultZoom", 11) or 11),
        "useProxy": use_proxy,
    }
    if use_proxy:
        payload["serviceHost"] = build_service_host(public_base_url)
    else:
        payload["securityCode"] = config.get("securityCode", "")
        payload["securityCodeExposed"] = True
    return payload
