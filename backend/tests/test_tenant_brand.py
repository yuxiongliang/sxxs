"""租户站点品牌：匿名可读、租户可改、权限受控。"""

from __future__ import annotations

from tests.conftest import bearer


async def test_public_brand_falls_back_to_name(client):
    response = await client.get("/api/v1/public/brand?tenant=demo")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["slug"] == "demo"
    # 没设置 display_name 时必须回落到 name，而不是返回空串
    assert data["display_name"]
    assert data["display_name"] == data["name"]


async def test_public_brand_rejects_unknown_tenant(client):
    response = await client.get("/api/v1/public/brand?tenant=no-such-tenant")
    assert response.status_code == 404, response.text


async def test_tenant_can_update_own_brand_and_public_endpoint_reflects_it(client, admin_token):
    saved = await client.put(
        "/api/v1/tenant/brand",
        headers=bearer(admin_token),
        json={
            "display_name": "我的租赁站",
            "logo_url": "/api/v1/attachments/public/1",
            "theme_color": "#722ed1",
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["display_name"] == "我的租赁站"

    public = await client.get("/api/v1/public/brand?tenant=demo")
    assert public.json()["data"]["display_name"] == "我的租赁站"
    assert public.json()["data"]["theme_color"] == "#722ed1"


async def test_buyer_cannot_update_brand(client, customer_token):
    response = await client.put(
        "/api/v1/tenant/brand",
        headers=bearer(customer_token),
        json={"display_name": "抢站名"},
    )
    assert response.status_code == 403, response.text
