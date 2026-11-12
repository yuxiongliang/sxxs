"""按月抽佣台账：GMV × 类目比例，买断/自定义档期豁免。

口径（与用户确认）：基数=当月已支付订单金额；比例=租户所属业务类目；
买断（lifetime）与自定义档期（custom）套餐的租户恒为 0。
"""

from __future__ import annotations

from tests.conftest import bearer

REPORT = "/api/v1/platform/commission-report"


async def _make_category(client, token, code="test-cat", bps=500) -> int:
    created = await client.post(
        "/api/v1/platform/service-categories",
        headers=bearer(token),
        json={"code": code, "name": f"类目 {code}", "commission_bps": bps},
    )
    assert created.status_code == 200, created.text
    return created.json()["data"]["id"]


async def _assign(client, token, tenant_id: int, category_id: int | None) -> None:
    response = await client.put(
        f"/api/v1/platform/tenants/{tenant_id}/service-category",
        headers=bearer(token),
        json={"service_category_id": category_id},
    )
    assert response.status_code == 200, response.text


async def test_requires_platform_token(client, admin_token):
    response = await client.get(REPORT, headers=bearer(admin_token))
    assert response.status_code == 401, response.text


async def test_commission_follows_category_rate(client, platform_token):
    category_id = await _make_category(client, platform_token, "rate-cat", 500)
    await _assign(client, platform_token, 1, category_id)

    report = (await client.get(REPORT, headers=bearer(platform_token))).json()["data"]
    demo = next(row for row in report["rows"] if row["tenant_id"] == 1)
    assert demo["service_category"]["commission_bps"] == 500
    assert demo["waived"] is False
    assert demo["rate_bps"] == 500
    # 公式必须自洽：应抽佣 = GMV × bps / 10000（向下取整）
    assert demo["commission_cents"] == demo["gmv_cents"] * 500 // 10000
    assert report["total_commission_cents"] == sum(
        row["commission_cents"] for row in report["rows"]
    )


async def test_buyout_tenant_is_waived_even_with_category(client, platform_token):
    category_id = await _make_category(client, platform_token, "waive-cat", 800)
    created = await client.post(
        "/api/v1/platform/tenants",
        headers=bearer(platform_token),
        json={
            "name": "买断测试站",
            "slug": "buyout-market",
            "email": "owner-buyout@example.com",
            "nickname": "站长",
            "password": "Buyout@123456",
            "service_category_id": category_id,
        },
    )
    assert created.status_code == 200, created.text
    tenant_id = created.json()["data"]["id"]

    report = (await client.get(REPORT, headers=bearer(platform_token))).json()["data"]
    row = next(item for item in report["rows"] if item["tenant_id"] == tenant_id)
    assert row["plan_period"] == "lifetime", "新租户默认买断"
    assert row["waived"] is True
    assert row["rate_bps"] == 0
    assert row["commission_cents"] == 0


async def test_bad_month_is_rejected(client, platform_token):
    response = await client.get(
        REPORT, headers=bearer(platform_token), params={"month": "2026-13-01"}
    )
    assert response.status_code == 400, response.text
