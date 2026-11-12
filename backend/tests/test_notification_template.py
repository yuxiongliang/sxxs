"""通知模板：变量白名单、渲染校验、两类 scope 隔离。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.services.notification_template import render, validate_template_variables
from tests.conftest import bearer


def test_render_substitutes_variables():
    text = "欢迎 {{tenant_name}}，订单 {{order_no}} 已完成"
    assert render(text, {"tenant_name": "李思的二手好物", "order_no": "SO-1"}) == (
        "欢迎 李思的二手好物，订单 SO-1 已完成"
    )


def test_render_rejects_missing_variable():
    # 把 {{tenant_name}} 原样发给买家是事故，必须拦住
    with pytest.raises(HTTPException) as exc:
        render("欢迎 {{tenant_name}}", {})
    assert exc.value.status_code == 400
    assert "tenant_name" in str(exc.value.detail)


def test_template_variable_whitelist():
    assert validate_template_variables("{{tenant_name}}") == ["tenant_name"]
    with pytest.raises(HTTPException):
        validate_template_variables("{{ evil_expression }}")


async def test_platform_can_save_template_and_extracts_variables(client, platform_token):
    response = await client.put(
        "/api/v1/platform/notification-templates/tenant/order_paid",
        headers=bearer(platform_token),
        json={
            "name": "订单已支付",
            "channel": "inbox",
            "subject": "{{tenant_name}} 订单支付成功",
            "body": "你好 {{buyer_name}}，订单 {{order_no}} 已支付",
            "enabled": True,
            "mandatory": True,
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    # 传老的 tenant 会被归一成 tenant_buyer（买家档），避免历史数据消失
    assert data["scope"] == "tenant_buyer"
    assert set(data["variables"]) == {"tenant_name", "buyer_name", "order_no"}
    assert data["mandatory"] is True


async def test_platform_template_with_unknown_variable_is_rejected(client, platform_token):
    response = await client.put(
        "/api/v1/platform/notification-templates/tenant/bad",
        headers=bearer(platform_token),
        json={"name": "坏模板", "body": "{{hack_me}}"},
    )
    assert response.status_code == 400, response.text


async def test_tenant_sees_only_enabled_tenant_scope_templates(client, admin_token, platform_token):
    await client.put(
        "/api/v1/platform/notification-templates/tenant/greeting",
        headers=bearer(platform_token),
        json={"name": "问候", "body": "你好 {{tenant_name}}", "enabled": True},
    )
    await client.put(
        "/api/v1/platform/notification-templates/tenant/disabled_one",
        headers=bearer(platform_token),
        json={"name": "已停用", "body": "x", "enabled": False},
    )
    await client.put(
        "/api/v1/platform/notification-templates/platform/sub_expiring",
        headers=bearer(platform_token),
        json={"name": "平台提醒", "body": "订阅即将到期", "enabled": True},
    )

    response = await client.get("/api/v1/notifications/templates", headers=bearer(admin_token))
    assert response.status_code == 200, response.text
    codes = [item["code"] for item in response.json()["data"]]
    assert "greeting" in codes
    assert "disabled_one" not in codes
    assert "sub_expiring" not in codes, "平台→租户的模板不能出现在租户端"


async def test_send_notification_renders_template(client, admin_token, platform_token):
    """端到端：发送时真用了模板，且 {{tenant_name}} 被渲染。

    没有这条测试的话，以后有人改 send_notification 很容易把渲染悄悄绕过，
    而单元测试仍然全绿。
    """
    await client.put(
        "/api/v1/platform/notification-templates/tenant/order_paid",
        headers=bearer(platform_token),
        json={
            "name": "订单支付成功",
            "channel": "inbox",
            "subject": "",
            "body": "你好，来自 {{tenant_name}}",
            "enabled": True,
            "mandatory": True,
        },
    )

    response = await client.post(
        "/api/v1/notifications/send",
        headers=bearer(admin_token),
        json={
            "title": "占位标题",
            "channel": "inbox",
            "template": "order_paid",
            "audience": "all",
            "content": "",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert "{{" not in data["content"], "渲染失败，占位符被原样发出"
    assert "Demo C2C Marketplace" in data["content"]


async def test_send_notification_rejects_missing_template(client, admin_token):
    response = await client.post(
        "/api/v1/notifications/send",
        headers=bearer(admin_token),
        json={
            "title": "占位标题",
            "channel": "inbox",
            "template": "no_such_template",
            "audience": "all",
            "content": "",
        },
    )
    assert response.status_code == 400, response.text


async def test_notification_prefs_mandatory_inbox_cannot_be_disabled(client, admin_token):
    """站内信强制开启（欠费/安全/合规通知必须送达），只能关短信/邮件。"""
    prefs = await client.get("/api/v1/notifications/prefs", headers=bearer(admin_token))
    assert prefs.status_code == 200, prefs.text
    channels = {item["channel"]: item for item in prefs.json()["data"]["channels"]}
    assert channels["inbox"]["mandatory"] is True
    assert channels["sms"]["enabled"] is True

    saved = await client.put(
        "/api/v1/notifications/prefs",
        headers=bearer(admin_token),
        json={"channel": "sms", "enabled": False},
    )
    assert saved.status_code == 200, saved.text
    again = await client.get("/api/v1/notifications/prefs", headers=bearer(admin_token))
    sms = next(
        item for item in again.json()["data"]["channels"] if item["channel"] == "sms"
    )
    assert sms["enabled"] is False

    blocked = await client.put(
        "/api/v1/notifications/prefs",
        headers=bearer(admin_token),
        json={"channel": "inbox", "enabled": False},
    )
    assert blocked.status_code == 400, blocked.text
