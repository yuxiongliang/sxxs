"""平台审计：平台改全站配置必须留痕，且租户侧看不到。"""

from __future__ import annotations

from tests.conftest import bearer


async def test_platform_setting_change_is_audited(client, platform_token):
    """改配置 → 平台审计能查到 platform.setting.update。

    没有这条断言，`record_platform` 被误删或不再生效时全量回归仍会全绿。
    """
    saved = await client.put(
        "/api/v1/platform/settings/amap",
        headers=bearer(platform_token),
        json={
            "enabled": True,
            "policy_locked": False,
            "config": {"enabled": True, "jsKey": "k", "webKey": "w"},
        },
    )
    assert saved.status_code == 200, saved.text

    response = await client.get("/api/v1/platform/audit", headers=bearer(platform_token))
    assert response.status_code == 200, response.text
    items = response.json()["data"]["list"]
    matched = [
        item
        for item in items
        if item["action"] == "platform.setting.update" and item["target_id"] == "amap"
    ]
    assert matched, f"未找到平台审计记录，实际：{[i['action'] for i in items][:5]}"
    assert matched[0]["after"]["enabled"] is True


async def test_tenant_audit_does_not_include_platform_rows(client, admin_token):
    """租户侧审计只能看到自己租户的行，平台行（tenant_id 为空）不可见。"""
    response = await client.get("/api/v1/audit-logs", headers=bearer(admin_token))
    assert response.status_code == 200, response.text
    items = response.json()["data"]["list"]
    assert all(item["tenant_id"] is not None for item in items), "租户侧不应看到平台审计"


async def test_tenant_token_cannot_read_platform_audit(client, admin_token):
    response = await client.get("/api/v1/platform/audit", headers=bearer(admin_token))
    assert response.status_code == 401, response.text
