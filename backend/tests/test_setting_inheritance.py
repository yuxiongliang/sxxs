"""配置继承：租户 / 平台 的取值优先级与密钥脱敏。

四条优先级必须各自有测试，否则「平台没配就切 inherit」这类上线事故无法提前发现：
  1. 租户 override 优先于平台
  2. 平台 enabled 时覆盖租户
  3. 平台未启用 → **回落租户历史配置**（安全网）
  4. 都没有 → 代码默认值

另外覆盖两条硬约束：支付不允许跟随系统；平台锁定后租户不可自定义。
"""

from __future__ import annotations

from tests.conftest import bearer


async def _platform_set(
    client,
    platform_token,
    category: str,
    *,
    enabled: bool,
    config: dict,
    policy_locked: bool = False,
) -> None:
    response = await client.put(
        f"/api/v1/platform/settings/{category}",
        headers=bearer(platform_token),
        json={"enabled": enabled, "config": config, "policy_locked": policy_locked},
    )
    assert response.status_code == 200, response.text


async def _tenant_get(client, token, category: str) -> dict:
    response = await client.get(f"/api/v1/settings/{category}", headers=bearer(token))
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def _tenant_put(client, token, category: str, payload: dict):
    return await client.put(
        f"/api/v1/settings/{category}",
        headers=bearer(token),
        json=payload,
    )


async def test_platform_disabled_falls_back_to_tenant_config(client, admin_token):
    """平台没启用该类配置时，租户看到的是自己的历史配置（安全网）。"""
    data = await _tenant_get(client, admin_token, "amap")
    assert data["source"] == "inherit"
    assert data["effective_source"] == "tenant_fallback"
    assert data["platform_active"] is False


async def test_platform_enabled_overrides_tenant_and_masks_secrets(
    client, admin_token, platform_token
):
    await _platform_set(
        client,
        platform_token,
        "amap",
        enabled=True,
        config={
            "enabled": True,
            "jsKey": "platform-js",
            "securityCode": "platform-sc",
            "webKey": "platform-web",
        },
    )

    data = await _tenant_get(client, admin_token, "amap")
    assert data["effective_source"] == "inherit"
    assert data["platform_active"] is True
    assert data["config"]["jsKey"] == "platform-js", "jsKey 要给浏览器用，不能被遮"
    assert data["config"]["securityCode"] == "platform-sc"
    assert data["config"]["webKey"] == "******", "平台服务端密钥绝不下发给租户"
    assert "webKey" in data["masked_fields"]


async def test_tenant_override_wins_over_platform(client, admin_token, platform_token):
    await _platform_set(
        client,
        platform_token,
        "amap",
        enabled=True,
        config={"enabled": True, "jsKey": "platform-js", "webKey": "platform-web"},
    )
    saved = await _tenant_put(
        client,
        admin_token,
        "amap",
        {
            "source": "override",
            "enabled": True,
            "config": {"enabled": True, "jsKey": "mine-js", "webKey": "mine-web"},
        },
    )
    assert saved.status_code == 200, saved.text

    data = await _tenant_get(client, admin_token, "amap")
    assert data["source"] == "override"
    assert data["effective_source"] == "override"
    assert data["config"]["jsKey"] == "mine-js"
    assert data["masked_fields"] == [], "用自己的配置时不需要脱敏"


async def test_switching_back_to_inherit_keeps_tenant_config_for_fallback(
    client, admin_token, platform_token
):
    # 先存一份自己的配置
    await _tenant_put(
        client,
        admin_token,
        "sms",
        {
            "source": "override",
            "enabled": True,
            "config": {"accessKeyId": "my-key", "signName": "我的签名"},
        },
    )
    # 切回跟随系统，但平台没启用 → 应该继续用自己那份，而不是代码默认值
    await _tenant_put(
        client,
        admin_token,
        "sms",
        {
            "source": "inherit",
            "enabled": True,
            "config": {"accessKeyId": "my-key", "signName": "我的签名"},
        },
    )
    data = await _tenant_get(client, admin_token, "sms")
    assert data["source"] == "inherit"
    assert data["effective_source"] == "tenant_fallback"
    assert data["config"]["accessKeyId"] == "my-key"


async def test_payment_cannot_inherit(client, admin_token, platform_token):
    """平台只收订阅费，不代收业务款 —— 支付配置必须由租户自己填。"""
    await _platform_set(
        client,
        platform_token,
        "payment",
        enabled=True,
        config={"enabled": True, "alipay": {"appId": "platform-app"}},
    )
    response = await _tenant_put(
        client,
        admin_token,
        "payment",
        {"source": "inherit", "enabled": True, "config": {}},
    )
    assert response.status_code == 400, response.text

    data = await _tenant_get(client, admin_token, "payment")
    assert data["source"] == "override"
    assert data["inherit_allowed"] is False


async def test_policy_locked_forces_inherit_and_blocks_customization(
    client, admin_token, platform_token
):
    await _platform_set(
        client,
        platform_token,
        "email",
        enabled=True,
        config={
            "enabled": True,
            "host": "smtp.platform.com",
            "username": "platform@x.com",
            "password": "secret",
        },
        policy_locked=True,
    )

    data = await _tenant_get(client, admin_token, "email")
    assert data["policy_locked"] is True
    assert data["source"] == "forced_inherit"
    assert data["inherit_allowed"] is False
    assert data["config"]["password"] == "******"

    blocked = await _tenant_put(
        client,
        admin_token,
        "email",
        {"source": "override", "enabled": True, "config": {"host": "mine"}},
    )
    assert blocked.status_code == 403, blocked.text
