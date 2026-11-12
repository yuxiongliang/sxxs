"""SaaS billing: plans, subscriptions, usage/quota, invoices, tenant lifecycle.

Plan §16 Phase 5 acceptance criteria covered:
  plans / subscriptions / invoices / usage / quota / feature flags, plus
  tenant edit / suspend / resume / renew.
"""

from __future__ import annotations

import pytest

from app.models.tenant import Tenant
from tests.conftest import bearer

OTHER_TENANT = {
    "name": "Billing Other Tenant",
    "slug": "billing-other",
    "email": "billing-other@example.com",
    "nickname": "Billing Owner",
    "password": "Billing@123456",
}


async def _create_other_tenant(client, platform_token) -> dict:
    response = await client.post(
        "/api/v1/platform/tenants", headers=bearer(platform_token), json=OTHER_TENANT
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def _other_token(client) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": OTHER_TENANT["email"], "password": OTHER_TENANT["password"]},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["access_token"]


async def _subscribe_monthly(client, platform_token, tenant_id: int) -> None:
    """把租户切到一个按月套餐上 —— 新租户默认是终身买断，不按周期续费。"""
    plans = (
        await client.get(
            "/api/v1/platform/plans?include_archived=true", headers=bearer(platform_token)
        )
    ).json()["data"]
    monthly = next(plan for plan in plans if plan["code"] == "pro")
    response = await client.post(
        f"/api/v1/platform/tenants/{tenant_id}/subscription",
        headers=bearer(platform_token),
        json={"plan_id": monthly["id"]},
    )
    assert response.status_code == 200, response.text


# --------------------------------------------------------------------------- #
# Plans
# --------------------------------------------------------------------------- #


async def test_seeded_plan_catalogue(client, admin_token, platform_token):
    response = await client.get("/api/v1/platform/plans", headers=bearer(platform_token))
    assert response.status_code == 200, response.text
    plans = response.json()["data"]
    codes = {plan["code"] for plan in plans}
    # 平台只卖一个买断套餐：全功能 / 9999 元 / 终身 / 不抽佣
    assert codes == {"buyout"}
    buyout = plans[0]
    assert buyout["period"] == "lifetime"
    assert buyout["price_cents"] == 999900
    assert buyout["trial_days"] == 0
    assert buyout["quotas"] == {"products": None, "members": None}

    # 历史套餐下架但保留行（历史订阅/账单还引用它们）
    archived = await client.get(
        "/api/v1/platform/plans?include_archived=true", headers=bearer(platform_token)
    )
    archived_codes = {plan["code"] for plan in archived.json()["data"]}
    assert {"free", "pro", "enterprise"} <= archived_codes


async def test_create_plan_and_reject_duplicate_code(client, admin_token, platform_token):
    payload = {
        "code": "pytest-plan",
        "name": "测试套餐",
        "price_cents": 1000,
        "quotas": {"products": 10, "members": 3},
        "features": ["portal"],
    }
    created = await client.post(
        "/api/v1/platform/plans", headers=bearer(platform_token), json=payload
    )
    assert created.status_code == 200, created.text
    assert created.json()["data"]["code"] == "pytest-plan"

    duplicate = await client.post(
        "/api/v1/platform/plans", headers=bearer(platform_token), json=payload
    )
    assert duplicate.status_code == 409


async def test_update_plan(client, admin_token, platform_token):
    created = (
        await client.post(
            "/api/v1/platform/plans",
            headers=bearer(platform_token),
            json={"code": "pytest-plan-2", "name": "改前", "price_cents": 100},
        )
    ).json()["data"]

    updated = await client.put(
        f"/api/v1/platform/plans/{created['id']}",
        headers=bearer(platform_token),
        json={"name": "改后", "price_cents": 200},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["name"] == "改后"
    assert updated.json()["data"]["price_cents"] == 200


@pytest.mark.parametrize("code", ["UPPER", "has space", "a"])
async def test_plan_code_is_validated(client, admin_token, code, platform_token):
    response = await client.post(
        "/api/v1/platform/plans",
        headers=bearer(platform_token),
        json={"code": code, "name": "x"},
    )
    assert response.status_code == 422


# --------------------------------------------------------------------------- #
# Subscriptions & usage
# --------------------------------------------------------------------------- #


async def test_demo_tenant_is_on_the_pro_plan(client, admin_token, platform_token):
    report = (
        await client.get("/api/v1/platform/tenants/1/usage", headers=bearer(platform_token))
    ).json()["data"]
    assert report["plan"]["code"] == "pro"
    assert report["subscription"]["status"] in {"active", "trialing"}
    assert "im" in report["plan"]["features"]
    assert report["quotas"]["products"] == 5000


async def test_new_tenant_gets_the_buyout_plan_without_trial(client, admin_token, platform_token):
    created = await _create_other_tenant(client, platform_token)
    token = await _other_token(client)

    report = (
        await client.get(
            f"/api/v1/platform/tenants/{created['id']}/usage", headers=bearer(platform_token)
        )
    ).json()["data"]
    # 买断口径：没有试用、状态直接 active、周期是终身
    assert report["plan"]["code"] == "buyout"
    assert report["plan"]["period"] == "lifetime"
    assert report["subscription"]["status"] == "active"
    assert report["subscription"]["trial_end"] is None

    # The tenant can read its own subscription through the member-facing route.
    own = await client.get("/api/v1/tenant/subscription", headers=bearer(token))
    assert own.status_code == 200
    assert own.json()["data"]["plan"]["code"] == "buyout"


async def test_usage_counts_reflect_business_data(client, admin_token, platform_token):
    report = (
        await client.get("/api/v1/platform/tenants/1/usage", headers=bearer(platform_token))
    ).json()["data"]
    assert report["used"]["products"] >= 1
    assert report["used"]["members"] >= 1
    assert report["remaining"]["products"] == 5000 - report["used"]["products"]


async def test_change_plan(client, admin_token, platform_token):
    created = await _create_other_tenant(client, platform_token)
    archived_plans = (
        await client.get(
            "/api/v1/platform/plans?include_archived=true", headers=bearer(platform_token)
        )
    ).json()["data"]
    enterprise = next(plan for plan in archived_plans if plan["code"] == "enterprise")

    response = await client.post(
        f"/api/v1/platform/tenants/{created['id']}/subscription",
        headers=bearer(platform_token),
        json={"plan_id": enterprise["id"]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["plan_id"] == enterprise["id"]

    report = (
        await client.get(
            f"/api/v1/platform/tenants/{created['id']}/usage", headers=bearer(platform_token)
        )
    ).json()["data"]
    assert report["plan"]["code"] == "enterprise"
    assert "custom-domain" in report["plan"]["features"]


# --------------------------------------------------------------------------- #
# Quota enforcement
# --------------------------------------------------------------------------- #


async def test_member_quota_is_enforced(client, admin_token, db_session, platform_token):
    """A tenant on a plan with members=1 cannot add a second member."""
    created = await _create_other_tenant(client, platform_token)
    tiny = (
        await client.post(
            "/api/v1/platform/plans",
            headers=bearer(platform_token),
            json={"code": "tiny", "name": "极小套餐", "quotas": {"products": 1, "members": 1}},
        )
    ).json()["data"]
    await client.post(
        f"/api/v1/platform/tenants/{created['id']}/subscription",
        headers=bearer(platform_token),
        json={"plan_id": tiny["id"]},
    )

    token = await _other_token(client)
    blocked = await client.post(
        "/api/v1/users",
        headers=bearer(token),
        json={
            "username": "quota_victim",
            "nickname": "配额",
            "email": "quota_victim@example.com",
            "role": "viewer",
            "password": "Quota@123456",
        },
    )
    assert blocked.status_code == 403, blocked.text
    assert "配额" in blocked.json()["message"]


async def test_product_quota_is_enforced(
    client, admin_token, operator_token, db_session, platform_token
):
    """Switch the demo tenant to a products=0 plan and seller listing must fail."""
    zero = (
        await client.post(
            "/api/v1/platform/plans",
            headers=bearer(platform_token),
            json={"code": "zero-products", "name": "零商品", "quotas": {"products": 0}},
        )
    ).json()["data"]
    original = db_session  # keep the fixture alive for the transaction
    assert original is not None

    await client.post(
        "/api/v1/platform/tenants/1/subscription",
        headers=bearer(platform_token),
        json={"plan_id": zero["id"]},
    )

    response = await client.post(
        "/api/v1/portal/seller/products",
        headers=bearer(operator_token),
        json={"name": "配额拦截商品", "price_cents": 1000, "stock": 1},
    )
    assert response.status_code == 403
    assert "配额" in response.json()["message"]


# --------------------------------------------------------------------------- #
# Tenant lifecycle: edit / suspend / resume
# --------------------------------------------------------------------------- #


async def test_rename_tenant(client, admin_token, platform_token):
    created = await _create_other_tenant(client, platform_token)
    response = await client.put(
        f"/api/v1/platform/tenants/{created['id']}",
        headers=bearer(platform_token),
        json={"name": "改名后的租户"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["name"] == "改名后的租户"


async def test_suspend_blocks_the_tenant_and_resume_restores_it(
    client, admin_token, db_session, platform_token
):
    created = await _create_other_tenant(client, platform_token)
    token = await _other_token(client)

    # Before suspension the owner can use the API.
    assert (await client.get("/api/v1/auth/me", headers=bearer(token))).status_code == 200

    suspended = await client.post(
        f"/api/v1/platform/tenants/{created['id']}/suspend",
        headers=bearer(platform_token),
        json={"reason": "欠费"},
    )
    assert suspended.status_code == 200, suspended.text

    blocked = await client.get("/api/v1/auth/me", headers=bearer(token))
    assert blocked.status_code == 403, "a suspended tenant must fail closed"

    await client.post(
        f"/api/v1/platform/tenants/{created['id']}/resume", headers=bearer(platform_token)
    )
    restored = await client.get("/api/v1/auth/me", headers=bearer(token))
    assert restored.status_code == 200


async def test_demo_tenant_cannot_be_suspended(client, admin_token, platform_token):
    response = await client.post(
        "/api/v1/platform/tenants/1/suspend",
        headers=bearer(platform_token),
        json={"reason": "误操作"},
    )
    assert response.status_code == 400


# --------------------------------------------------------------------------- #
# Invoices & renew
# --------------------------------------------------------------------------- #


async def test_renew_creates_a_pending_invoice_and_extends_the_period(
    client, admin_token, db_session, platform_token
):
    created = await _create_other_tenant(client, platform_token)
    await _subscribe_monthly(client, platform_token, created["id"])
    before = (
        await client.get(
            f"/api/v1/platform/tenants/{created['id']}/usage", headers=bearer(platform_token)
        )
    ).json()["data"]["subscription"]

    renewed = await client.post(
        f"/api/v1/platform/tenants/{created['id']}/renew",
        headers=bearer(platform_token),
        json={"days": 30},
    )
    assert renewed.status_code == 200, renewed.text
    invoice = renewed.json()["data"]["invoice"]
    assert invoice["status"] == "pending"
    assert invoice["tenant_id"] == created["id"]

    after = (
        await client.get(
            f"/api/v1/platform/tenants/{created['id']}/usage", headers=bearer(platform_token)
        )
    ).json()["data"]["subscription"]
    assert after["current_period_end"] > before["current_period_end"]


async def test_pay_invoice_and_reject_double_payment(client, admin_token, platform_token):
    created = await _create_other_tenant(client, platform_token)
    await _subscribe_monthly(client, platform_token, created["id"])
    invoice = (
        await client.post(
            f"/api/v1/platform/tenants/{created['id']}/renew",
            headers=bearer(platform_token),
            json={"days": 30},
        )
    ).json()["data"]["invoice"]

    paid = await client.post(
        f"/api/v1/platform/invoices/{invoice['id']}/pay", headers=bearer(platform_token)
    )
    assert paid.status_code == 200
    assert paid.json()["data"]["status"] == "paid"
    assert paid.json()["data"]["paid_at"]

    again = await client.post(
        f"/api/v1/platform/invoices/{invoice['id']}/pay", headers=bearer(platform_token)
    )
    assert again.status_code == 400


async def test_invoices_are_filterable_by_tenant(client, admin_token, platform_token):
    created = await _create_other_tenant(client, platform_token)
    await _subscribe_monthly(client, platform_token, created["id"])
    await client.post(
        f"/api/v1/platform/tenants/{created['id']}/renew",
        headers=bearer(platform_token),
        json={"days": 30},
    )

    mine = await client.get(
        "/api/v1/platform/invoices",
        headers=bearer(platform_token),
        params={"tenant_id": created["id"]},
    )
    assert mine.status_code == 200
    assert all(item["tenant_id"] == created["id"] for item in mine.json()["data"])
    assert mine.json()["data"], "the renewed tenant must have an invoice"


async def test_tenant_list_includes_plan_information(client, admin_token, platform_token):
    await _create_other_tenant(client, platform_token)
    response = await client.get("/api/v1/platform/tenants-list", headers=bearer(platform_token))
    assert response.status_code == 200
    rows = response.json()["data"]
    assert rows
    assert all("plan" in row and "used" in row for row in rows)


# --------------------------------------------------------------------------- #
# Authorization
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "path",
    ["/api/v1/platform/plans", "/api/v1/platform/invoices", "/api/v1/platform/tenants-list"],
)
async def test_billing_console_is_platform_only(client, operator_token, customer_token, path):
    # 401 而非 403：租户 token 的 aud 是 admin，平台接口只认 aud=platform，JWT audience 校验直接判未认证。
    assert (await client.get(path, headers=bearer(operator_token))).status_code == 401
    assert (await client.get(path, headers=bearer(customer_token))).status_code == 401


async def test_tenant_owner_cannot_suspend_itself(client, admin_token, platform_token):
    created = await _create_other_tenant(client, platform_token)
    token = await _other_token(client)
    response = await client.post(
        f"/api/v1/platform/tenants/{created['id']}/suspend",
        headers=bearer(token),
        json={"reason": "自我停用"},
    )
    assert response.status_code == 401


async def test_suspended_tenant_rows_remain_queryable_by_platform(
    client, admin_token, db_session, platform_token
):
    created = await _create_other_tenant(client, platform_token)
    await client.post(
        f"/api/v1/platform/tenants/{created['id']}/suspend",
        headers=bearer(platform_token),
        json={"reason": "验证"},
    )
    tenant = await db_session.get(Tenant, created["id"])
    assert tenant is not None and tenant.status == "suspended"

    rows = (
        await client.get("/api/v1/platform/tenants-list", headers=bearer(platform_token))
    ).json()["data"]
    row = next(item for item in rows if item["id"] == created["id"])
    assert row["status"] == "suspended"
