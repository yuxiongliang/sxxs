"""高德地图接入：配置、错误码翻译、key 不泄漏、静态地图与安全密钥代理。

设计要点（也是本文件的断言重点）：

* `webKey` 只给后端用，任何下发到浏览器的接口都不能出现它。
* 安全密钥默认不下发明文，走 /_AMapService 代理（serviceHost）。
* 高德用 {status, info, infocode} 表达失败，HTTP 恒 200，必须翻译成可读错误。
"""

from __future__ import annotations

import pytest

from app.api import proxy_amap
from app.services import amap as amap_module
from tests.conftest import bearer


class _FakeResponse:
    def __init__(self, payload=None, content=b"", content_type="application/json"):
        self._payload = payload
        self.content = content
        self.status_code = 200
        self.headers = {"content-type": content_type}

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


class _FakeClient:
    last_call: tuple[str, dict[str, str]] | None = None

    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def get(self, path: str, params: dict[str, str] | None = None):
        _FakeClient.last_call = (path, dict(params or {}))
        return self._response


def _patch_http(monkeypatch, response):
    monkeypatch.setattr(amap_module.httpx, "AsyncClient", lambda **_kwargs: _FakeClient(response))


async def test_default_config_is_returned_without_secrets(client, admin_token, db_session):
    response = await client.get("/api/v1/settings/amap", headers=bearer(admin_token))
    assert response.status_code == 200, response.text
    config = response.json()["data"]["config"]
    assert config["useProxy"] is True
    assert config["webKey"] == ""
    assert "defaultCenter" in config


async def test_customer_cannot_read_amap_settings(client, customer_token):
    response = await client.get("/api/v1/settings/amap", headers=bearer(customer_token))
    assert response.status_code == 403


async def test_operator_can_read_amap_settings(client, operator_token):
    response = await client.get("/api/v1/settings/amap", headers=bearer(operator_token))
    assert response.status_code == 200, response.text


async def test_saving_amap_settings_persists(client, admin_token):
    payload = {
        "enabled": True,
        "config": {
            "jsKey": "js-key-demo",
            "securityCode": "secret-demo",
            "webKey": "web-key-demo",
            "defaultCenter": "121.473701,31.230416",
            "defaultZoom": 13,
            "useProxy": True,
        },
    }
    saved = await client.put("/api/v1/settings/amap", headers=bearer(admin_token), json=payload)
    assert saved.status_code == 200, saved.text
    again = await client.get("/api/v1/settings/amap", headers=bearer(admin_token))
    config = again.json()["data"]["config"]
    assert config["jsKey"] == "js-key-demo"
    assert config["defaultCenter"] == "121.473701,31.230416"


async def test_map_config_hides_web_key_and_security_code_when_proxying(client, admin_token):
    await client.put(
        "/api/v1/settings/amap",
        headers=bearer(admin_token),
        json={
            "enabled": True,
            "config": {
                "jsKey": "js-key-demo",
                "securityCode": "secret-demo",
                "webKey": "web-key-demo",
                "useProxy": True,
            },
        },
    )
    response = await client.get("/api/v1/amap/config", headers=bearer(admin_token))
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert "webKey" not in data
    assert "securityCode" not in data, "代理模式下安全密钥绝不能下发"
    assert data["serviceHost"].endswith("/_AMapService")
    assert data["jsKey"] == "js-key-demo"


async def test_map_config_exposes_security_code_only_in_plaintext_mode(client, admin_token):
    await client.put(
        "/api/v1/settings/amap",
        headers=bearer(admin_token),
        json={"enabled": True, "config": {"securityCode": "secret-demo", "useProxy": False}},
    )
    data = (await client.get("/api/v1/amap/config", headers=bearer(admin_token))).json()["data"]
    assert data["securityCode"] == "secret-demo"
    assert data["useProxy"] is False


async def test_test_connection_requires_a_web_service_key(client, admin_token):
    await client.put(
        "/api/v1/settings/amap",
        headers=bearer(admin_token),
        json={"enabled": True, "config": {"jsKey": "only-js-key", "webKey": ""}},
    )
    result = await client.post("/api/v1/settings/amap/test", headers=bearer(admin_token), json={})
    assert result.status_code == 200, result.text
    body = result.json()["data"]
    assert body["success"] is False
    assert "Web服务 key" in body["message"]


async def test_test_connection_translates_platform_mismatch(client, admin_token, monkeypatch):
    """10009 = 拿 JS API key 调 Web 服务，最常见的坑。"""
    _patch_http(
        monkeypatch,
        _FakeResponse({"status": "0", "info": "USERKEY_PLAT_NOMATCH", "infocode": "10009"}),
    )
    await client.put(
        "/api/v1/settings/amap",
        headers=bearer(admin_token),
        json={"enabled": True, "config": {"webKey": "js-key-by-mistake"}},
    )
    result = await client.post("/api/v1/settings/amap/test", headers=bearer(admin_token), json={})
    body = result.json()["data"]
    assert body["success"] is False
    assert body["detail"]["infocode"] == "10009"
    assert "平台不符" in body["message"]


async def test_test_connection_success(client, admin_token, monkeypatch):
    _patch_http(
        monkeypatch,
        _FakeResponse(
            {
                "status": "1",
                "info": "OK",
                "infocode": "10000",
                "count": "1",
                "geocodes": [
                    {
                        "formatted_address": "北京市朝阳区阜通东大街6号",
                        "location": "116.482,39.996",
                        "level": "门牌号",
                    }
                ],
            }
        ),
    )
    await client.put(
        "/api/v1/settings/amap",
        headers=bearer(admin_token),
        json={"enabled": True, "config": {"webKey": "web-key-demo"}},
    )
    result = await client.post("/api/v1/settings/amap/test", headers=bearer(admin_token), json={})
    body = result.json()["data"]
    assert body["success"] is True
    assert body["detail"]["location"] == "116.482,39.996"


async def test_regeo_returns_structured_address(client, admin_token, monkeypatch):
    _patch_http(
        monkeypatch,
        _FakeResponse(
            {
                "status": "1",
                "info": "OK",
                "infocode": "10000",
                "regeocode": {
                    "formatted_address": "北京市朝阳区望京街道阜通东大街6号",
                    "addressComponent": {
                        "province": "北京市",
                        "city": [],
                        "district": "朝阳区",
                        "township": "望京街道",
                        "adcode": "110105",
                    },
                    "pois": [],
                },
            }
        ),
    )
    await client.put(
        "/api/v1/settings/amap",
        headers=bearer(admin_token),
        json={"enabled": True, "config": {"webKey": "web-key-demo"}},
    )
    response = await client.get(
        "/api/v1/amap/regeo", headers=bearer(admin_token), params={"lng": 116.482, "lat": 39.996}
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["district"] == "朝阳区"
    assert data["city"] == "北京市", "高德对直辖市返回 city=[]，必须回退到 province"


async def test_regeo_validates_coordinates(client, admin_token):
    response = await client.get(
        "/api/v1/amap/regeo", headers=bearer(admin_token), params={"lng": 999, "lat": 39}
    )
    assert response.status_code == 422


async def test_static_map_returns_image_bytes(client, admin_token, monkeypatch):
    png = b"\x89PNG\r\n\x1a\nfake"
    _patch_http(monkeypatch, _FakeResponse(None, content=png, content_type="image/png"))
    await client.put(
        "/api/v1/settings/amap",
        headers=bearer(admin_token),
        json={"enabled": True, "config": {"webKey": "web-key-demo"}},
    )
    response = await client.get(
        "/api/v1/amap/static-map", headers=bearer(admin_token), params={"lng": 116.4, "lat": 39.9}
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.content == png


async def test_amap_error_maps_to_http_429_when_quota_exhausted(client, admin_token, monkeypatch):
    _patch_http(
        monkeypatch,
        _FakeResponse({"status": "0", "info": "DAILY_QUERY_OVER_LIMIT", "infocode": "10003"}),
    )
    await client.put(
        "/api/v1/settings/amap",
        headers=bearer(admin_token),
        json={"enabled": True, "config": {"webKey": "web-key-demo"}},
    )
    response = await client.get(
        "/api/v1/amap/regeo", headers=bearer(admin_token), params={"lng": 116.4, "lat": 39.9}
    )
    assert response.status_code == 429


async def test_security_proxy_injects_jscode(client, admin_token, monkeypatch):
    """/_AMapService 代理必须把安全密钥注入 jscode，且不需要登录态。

    代理是给浏览器 JS SDK 调用的无鉴权端点，它用独立连接读配置（不能依赖请求上下文），
    只从 Host 头判断是哪个租户的密钥；测试里直接桩住 _security_code，锁定「拿到密钥后
    必须注入 jscode」这个契约。
    """
    _patch_http(monkeypatch, _FakeResponse({"status": "1", "info": "OK"}))

    async def _fake_code(_request) -> str:
        return "secret-demo"

    monkeypatch.setattr(proxy_amap, "_security_code", _fake_code)
    response = await client.get("/_AMapService/v3/geocode/geo?address=%E5%8C%97%E4%BA%AC")
    assert response.status_code == 200, response.text
    assert _FakeClient.last_call is not None, "代理没有发出上游请求"
    _path, params = _FakeClient.last_call
    assert params["jscode"] == "secret-demo"
    assert params["address"] == "北京"


async def test_parse_location_rejects_bad_input():
    with pytest.raises(ValueError):
        amap_module.parse_location("116.4")
    with pytest.raises(ValueError):
        amap_module.parse_location("999,39")
    assert amap_module.parse_location("116.4, 39.9") == (116.4, 39.9)
