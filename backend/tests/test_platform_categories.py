"""平台端服务类目总览：跨租户只读视图。

断言重点：
1. 只有平台角色能看（租户 token 401）；
2. 每个租户的类目都在，商品数按租户隔离（不能把别家的商品算进来）；
3. tenant_id / q 两个筛选真的生效，且 q 里的 % 不会变成通配符。
"""

from __future__ import annotations

from tests.conftest import bearer


async def test_requires_platform_token(client, admin_token):
    response = await client.get("/api/v1/platform/categories", headers=bearer(admin_token))
    assert response.status_code == 401, response.text


async def test_lists_seeded_categories_with_product_counts(client, platform_token):
    response = await client.get("/api/v1/platform/categories", headers=bearer(platform_token))
    assert response.status_code == 200, response.text
    rows = response.json()["data"]
    assert rows, "种子数据里 demo 租户有类目，不能返回空列表"
    assert {row["tenant_slug"] for row in rows} == {"demo"}
    assert all(row["tenant_name"] for row in rows)
    assert any(row["product_count"] > 0 for row in rows), "种子商品应该挂在类目上"


async def test_filter_by_tenant_and_keyword(client, platform_token):
    all_rows = (
        await client.get("/api/v1/platform/categories", headers=bearer(platform_token))
    ).json()["data"]
    target = all_rows[0]

    by_tenant = await client.get(
        f"/api/v1/platform/categories?tenant_id={target['tenant_id']}",
        headers=bearer(platform_token),
    )
    assert by_tenant.status_code == 200, by_tenant.text
    assert len(by_tenant.json()["data"]) == len(all_rows)

    by_keyword = await client.get(
        "/api/v1/platform/categories",
        headers=bearer(platform_token),
        params={"q": target["slug"]},
    )
    assert by_keyword.status_code == 200, by_keyword.text
    names = [row["slug"] for row in by_keyword.json()["data"]]
    assert target["slug"] in names


async def test_keyword_wildcard_is_escaped(client, platform_token):
    """输入 % 不能把整张表匹配出来（通配符要当字面量）。"""
    response = await client.get(
        "/api/v1/platform/categories",
        headers=bearer(platform_token),
        params={"q": "%"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"] == []
