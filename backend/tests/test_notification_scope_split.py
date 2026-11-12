"""通知模板作用域拆分：租户 → 买家 / 租户 → 卖家 分开管理。

锁死四件事：
1. 买家、卖家两个作用域各自独立可见，不再混在一档；
2. 历史 `tenant` 作用域按别名落成 `tenant_buyer`，老数据不会消失；
3. 租户端能看到买家 + 卖家两份清单（它只读）；
4. 同一 code 同时存在于买家/卖家时，发送必须报错 —— 猜错就是把卖家邮件发给买家。
"""

from __future__ import annotations

from tests.conftest import bearer


async def _save(client, platform_token, scope: str, code: str, name: str, enabled: bool = True):
    return await client.put(
        f"/api/v1/platform/notification-templates/{scope}/{code}",
        headers=bearer(platform_token),
        json={
            "name": name,
            "channel": "inbox",
            "body": "你好 {{tenant_name}}",
            "enabled": enabled,
            "mandatory": False,
        },
    )


async def _codes(client, platform_token, scope: str) -> list[str]:
    response = await client.get(
        f"/api/v1/platform/notification-templates?scope={scope}",
        headers=bearer(platform_token),
    )
    assert response.status_code == 200, response.text
    return [row["code"] for row in response.json()["data"]]


async def test_buyer_and_seller_scopes_are_listed_separately(client, platform_token):
    await _save(client, platform_token, "tenant_buyer", "order_paid", "买家：订单已支付")
    await _save(client, platform_token, "tenant_seller", "order_created", "卖家：新订单")

    assert await _codes(client, platform_token, "tenant_buyer") == ["order_paid"]
    assert await _codes(client, platform_token, "tenant_seller") == ["order_created"]


async def test_legacy_tenant_scope_is_stored_as_buyer(client, platform_token):
    saved = await _save(client, platform_token, "tenant", "legacy_one", "老模板")
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["scope"] == "tenant_buyer", "老作用域要归一成买家档"

    assert "legacy_one" in await _codes(client, platform_token, "tenant_buyer")


async def test_unknown_scope_is_rejected(client, platform_token):
    response = await _save(client, platform_token, "tenant_both", "x", "混用")
    assert response.status_code == 400, response.text


async def test_variable_catalog_carries_chinese_annotations(client, platform_token):
    response = await client.get(
        "/api/v1/platform/notification-templates/variables",
        headers=bearer(platform_token),
    )
    assert response.status_code == 200, response.text
    rows = response.json()["data"]
    assert [row["name"] for row in rows] == [
        "tenant_name",
        "tenant_domain",
        "buyer_name",
        "order_no",
        "amount",
        "site_url",
        "support_email",
    ]
    for row in rows:
        assert row["label"] and row["description"] and row["example"], row["name"]
    assert "站点名称" in rows[0]["label"]
    assert "short_name" not in [row["name"] for row in rows], (
        "简称没有独立数据源，和 tenant_name 同值，已删除"
    )


async def test_tenant_side_sees_both_audiences(client, admin_token, platform_token):
    await _save(client, platform_token, "tenant_buyer", "buyer_tpl", "买家模板")
    await _save(client, platform_token, "tenant_seller", "seller_tpl", "卖家模板")

    response = await client.get("/api/v1/notifications/templates", headers=bearer(admin_token))
    assert response.status_code == 200, response.text
    codes = {row["code"] for row in response.json()["data"]}
    assert {"buyer_tpl", "seller_tpl"} <= codes


async def test_send_rejects_code_that_exists_in_both_audiences(client, admin_token, platform_token):
    await _save(client, platform_token, "tenant_buyer", "dup_tpl", "买家版")
    await _save(client, platform_token, "tenant_seller", "dup_tpl", "卖家版")

    response = await client.post(
        "/api/v1/notifications/send",
        headers=bearer(admin_token),
        json={
            "title": "占位",
            "channel": "inbox",
            "template": "dup_tpl",
            "audience": "all",
            "content": "",
        },
    )
    assert response.status_code == 400, response.text
    message = response.json()["message"]
    assert "tenant_buyer" in message and "tenant_seller" in message
