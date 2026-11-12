"""平台级业务类目：类目本身 + 租户归类 + 开通租户时归类。

断言重点：
1. 类目决定抽佣比例（万分比），改比例只影响后续计算，不碰历史；
2. code 唯一、不能重复建；归档后的类目不能再分配新租户；
3. 开通租户时带类目 → tenants-list 里就能看到归属；取消归类后变 null。
"""

from __future__ import annotations

from tests.conftest import bearer

PLATFORM = "/api/v1/platform/service-categories"


async def _create(client, token, code: str, bps: int = 500):
    return await client.post(
        PLATFORM,
        headers=bearer(token),
        json={"code": code, "name": f"类目 {code}", "commission_bps": bps},
    )


async def _tenant_id(client, token, slug: str = "demo") -> int:
    rows = (await client.get("/api/v1/platform/tenants", headers=bearer(token))).json()["data"]
    return next(row["id"] for row in rows if row["slug"] == slug)


async def _tenants_list_row(client, token, tenant_id: int) -> dict:
    rows = (await client.get("/api/v1/platform/tenants-list", headers=bearer(token))).json()["data"]
    return next(row for row in rows if row["id"] == tenant_id)


async def test_requires_platform_token(client, admin_token):
    response = await client.get(PLATFORM, headers=bearer(admin_token))
    assert response.status_code == 401, response.text


async def test_create_and_update_commission(client, platform_token):
    created = await _create(client, platform_token, "second-hand", 500)
    assert created.status_code == 200, created.text
    data = created.json()["data"]
    assert data["commission_bps"] == 500
    assert data["status"] == "active"

    updated = await client.put(
        f"{PLATFORM}/{data['id']}",
        headers=bearer(platform_token),
        json={"commission_bps": 300, "name": "二手交易"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["commission_bps"] == 300
    assert updated.json()["data"]["name"] == "二手交易"


async def test_duplicate_code_conflicts(client, platform_token):
    assert (await _create(client, platform_token, "dup-cat")).status_code == 200
    again = await _create(client, platform_token, "dup-cat")
    assert again.status_code == 409, again.text


async def test_assign_tenant_and_see_it_in_tenant_list(client, platform_token):
    category = (await _create(client, platform_token, "svc-local", 300)).json()["data"]
    tenant_id = await _tenant_id(client, platform_token)

    assigned = await client.put(
        f"/api/v1/platform/tenants/{tenant_id}/service-category",
        headers=bearer(platform_token),
        json={"service_category_id": category["id"]},
    )
    assert assigned.status_code == 200, assigned.text

    row = await _tenants_list_row(client, platform_token, tenant_id)
    assert row["service_category"]["id"] == category["id"]
    assert row["service_category"]["commission_bps"] == 300

    cleared = await client.put(
        f"/api/v1/platform/tenants/{tenant_id}/service-category",
        headers=bearer(platform_token),
        json={"service_category_id": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert (await _tenants_list_row(client, platform_token, tenant_id))["service_category"] is None


async def test_archived_category_cannot_be_assigned(client, platform_token):
    category = (await _create(client, platform_token, "legacy-cat")).json()["data"]
    await client.put(
        f"{PLATFORM}/{category['id']}",
        headers=bearer(platform_token),
        json={"status": "archived"},
    )
    tenant_id = await _tenant_id(client, platform_token)
    response = await client.put(
        f"/api/v1/platform/tenants/{tenant_id}/service-category",
        headers=bearer(platform_token),
        json={"service_category_id": category["id"]},
    )
    assert response.status_code == 400, response.text


async def test_new_tenant_can_be_created_with_category(client, platform_token):
    category = (await _create(client, platform_token, "new-tenant-cat", 800)).json()["data"]
    created = await client.post(
        "/api/v1/platform/tenants",
        headers=bearer(platform_token),
        json={
            "name": "归类测试站",
            "slug": "categorized-market",
            "email": "owner-categorized@example.com",
            "nickname": "站长",
            "password": "Categorized@123456",
            "service_category_id": category["id"],
        },
    )
    assert created.status_code == 200, created.text
    tenant_id = created.json()["data"]["id"]

    row = await _tenants_list_row(client, platform_token, tenant_id)
    assert row["service_category"]["code"] == "new-tenant-cat"
    assert row["service_category"]["commission_bps"] == 800
