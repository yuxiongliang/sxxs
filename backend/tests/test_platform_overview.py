"""平台运维概览：品牌 / 支付 / 域名 三项状态的聚合。"""

from __future__ import annotations

from tests.conftest import bearer


async def test_overview_reports_brand_and_payment_state(client, admin_token, platform_token):
    await client.put(
        "/api/v1/tenant/brand",
        headers=bearer(admin_token),
        json={"display_name": "概览测试站"},
    )
    await client.put(
        "/api/v1/settings/payment",
        headers=bearer(admin_token),
        json={
            "source": "override",
            "enabled": True,
            "config": {"alipay": {"appId": "my-real-app-id"}},
        },
    )

    response = await client.get("/api/v1/platform/overview/tenants", headers=bearer(platform_token))
    assert response.status_code == 200, response.text
    rows = response.json()["data"]
    demo = next(item for item in rows if item["slug"] == "demo")
    assert demo["brand"]["display_name"] == "概览测试站"
    assert demo["brand"]["customized"] is True
    assert demo["payment"]["configured"] is True
    assert demo["payment"]["source"] == "override"
    assert demo["domain"]["supported"] is False


async def test_overview_flags_placeholder_payment_as_unconfigured(client, platform_token):
    """照抄默认占位 appId 不算已配置 —— 否则概览会误报「支付就绪」。"""
    response = await client.get("/api/v1/platform/overview/tenants", headers=bearer(platform_token))
    assert response.status_code == 200, response.text
    rows = response.json()["data"]
    acme = next(item for item in rows if item["slug"] == "acme")
    assert acme["payment"]["configured"] is False


async def test_overview_requires_platform_token(client, admin_token):
    response = await client.get("/api/v1/platform/overview/tenants", headers=bearer(admin_token))
    assert response.status_code == 401, response.text
