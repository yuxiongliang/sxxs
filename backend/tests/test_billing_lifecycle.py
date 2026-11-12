"""SaaS billing lifecycle: the recurring dunning / renewal cycle.

Before this module the `past_due` status was modelled but nothing ever produced
it: no scheduler, no expiry handling, no downgrade. A tenant could sit on an
expired paid plan forever.

Contract under test (`billing.run_billing_cycle`):

* paid plan, term expired  -> issue a pending invoice, subscription `past_due`
* free plan, term expired  -> silently roll the term forward, stays `active`
* `cancel_at_period_end`   -> `cancelled`, never billed again
* `past_due` past grace    -> downgrade to the free plan, void the overdue invoice
* paying the invoice        -> back to `active` (grace-period recovery)
* running twice in one term -> no duplicate invoices
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models.billing import Invoice, Plan, TenantSubscription
from app.services import billing as billing_service
from tests.conftest import bearer


async def _demo_subscription(db_session) -> TenantSubscription:
    subscription = await billing_service.get_subscription(db_session, 1)
    assert subscription is not None, "the demo tenant must be seeded with a subscription"
    return subscription


async def _plan(db_session, code: str) -> Plan:
    plan = (await db_session.execute(select(Plan).where(Plan.code == code))).scalars().first()
    assert plan is not None, f"plan {code} must be seeded"
    return plan


async def _expire(db_session, subscription: TenantSubscription, days: int = 1) -> None:
    subscription.current_period_end = datetime.now(UTC) - timedelta(days=days)
    await db_session.flush()


async def _invoices(db_session, subscription_id: int) -> list[Invoice]:
    rows = await db_session.execute(
        select(Invoice).where(Invoice.subscription_id == subscription_id).order_by(Invoice.id)
    )
    return list(rows.scalars().all())


async def test_paid_plan_goes_past_due_and_gets_billed(client, admin_token, db_session):
    subscription = await _demo_subscription(db_session)
    pro = await _plan(db_session, "pro")
    assert subscription.plan_id == pro.id, "the demo tenant must sit on the paid plan"
    await _expire(db_session, subscription)

    summary = await billing_service.run_billing_cycle(db_session)
    assert summary["invoiced"] >= 1

    await db_session.refresh(subscription)
    assert subscription.status == "past_due"
    invoices = await _invoices(db_session, subscription.id)
    assert invoices, "an expired paid term must be invoiced"
    assert invoices[0].status == "pending"
    assert invoices[0].amount_cents == pro.price_cents
    assert subscription.current_period_end > datetime.now(UTC), (
        "the new term must already be reserved so the cycle is not run twice"
    )

    logs = await client.get(
        "/api/v1/audit-logs",
        headers=bearer(admin_token),
        params={"pageSize": 100, "action": "subscription.past_due"},
    )
    rows = logs.json()["data"]["list"]
    assert any(row["target_id"] == str(subscription.id) for row in rows), (
        "going past due must be auditable"
    )


async def test_free_plan_rolls_the_term_forward_without_an_invoice(db_session):
    subscription = await _demo_subscription(db_session)
    subscription.plan_id = (await _plan(db_session, "free")).id
    subscription.status = "active"
    await _expire(db_session, subscription)
    before = len(await _invoices(db_session, subscription.id))

    summary = await billing_service.run_billing_cycle(db_session)

    await db_session.refresh(subscription)
    assert summary["renewed"] >= 1
    assert subscription.status == "active", "a free plan has nothing to collect"
    assert len(await _invoices(db_session, subscription.id)) == before
    assert subscription.current_period_end > datetime.now(UTC)


async def test_cancel_at_period_end_stops_the_subscription(db_session):
    subscription = await _demo_subscription(db_session)
    subscription.cancel_at_period_end = True
    await _expire(db_session, subscription)
    before = len(await _invoices(db_session, subscription.id))

    summary = await billing_service.run_billing_cycle(db_session)

    await db_session.refresh(subscription)
    assert summary["cancelled"] >= 1
    assert subscription.status == "cancelled"
    assert len(await _invoices(db_session, subscription.id)) == before, (
        "a cancelled subscription must never be billed again"
    )


async def test_overdue_invoice_downgrades_the_tenant_to_free(db_session):
    subscription = await _demo_subscription(db_session)
    await _expire(db_session, subscription)
    await billing_service.run_billing_cycle(db_session)
    await db_session.refresh(subscription)
    assert subscription.status == "past_due"

    invoice = (await _invoices(db_session, subscription.id))[0]
    invoice.due_at = datetime.now(UTC) - timedelta(days=30)
    await db_session.flush()

    summary = await billing_service.run_billing_cycle(db_session)

    await db_session.refresh(subscription)
    free = await _plan(db_session, "free")
    assert summary["downgraded"] >= 1
    assert subscription.plan_id == free.id, "an unpaid tenant must fall back to the free plan"
    assert subscription.status == "active", "a downgraded tenant keeps working, on free quotas"
    assert subscription.current_period_end > datetime.now(UTC)

    await db_session.refresh(invoice)
    assert invoice.status == "void", "the uncollectable invoice must not stay pending forever"


async def test_paying_the_invoice_restores_the_paid_plan(client, admin_token, db_session, platform_token):
    subscription = await _demo_subscription(db_session)
    pro = await _plan(db_session, "pro")
    await _expire(db_session, subscription)
    await billing_service.run_billing_cycle(db_session)
    await db_session.refresh(subscription)
    assert subscription.status == "past_due"

    invoice = (await _invoices(db_session, subscription.id))[0]
    paid = await client.post(
        f"/api/v1/platform/invoices/{invoice.id}/pay", headers=bearer(platform_token)
    )
    assert paid.status_code == 200, paid.text

    await db_session.refresh(subscription)
    assert subscription.status == "active"
    assert subscription.plan_id == pro.id, "paying the bill keeps the paid plan"


async def test_the_cycle_is_idempotent_within_a_term(db_session):
    subscription = await _demo_subscription(db_session)
    await _expire(db_session, subscription)
    await billing_service.run_billing_cycle(db_session)
    count = len(await _invoices(db_session, subscription.id))

    second = await billing_service.run_billing_cycle(db_session)

    assert len(await _invoices(db_session, subscription.id)) == count
    assert second["invoiced"] == 0
    assert second["downgraded"] == 0


async def test_expired_trial_bills_the_paid_plan(db_session):
    subscription = await _demo_subscription(db_session)
    pro = await _plan(db_session, "pro")
    subscription.status = "trialing"
    subscription.trial_end = datetime.now(UTC) - timedelta(days=1)
    await _expire(db_session, subscription)

    await billing_service.run_billing_cycle(db_session)

    await db_session.refresh(subscription)
    assert subscription.status == "past_due"
    invoices = await _invoices(db_session, subscription.id)
    assert invoices and invoices[0].amount_cents == pro.price_cents
    assert subscription.trial_end is not None


async def test_an_unexpired_subscription_is_untouched(db_session):
    subscription = await _demo_subscription(db_session)
    before = (
        subscription.status,
        subscription.plan_id,
        subscription.current_period_end,
        len(await _invoices(db_session, subscription.id)),
    )

    summary = await billing_service.run_billing_cycle(db_session)

    await db_session.refresh(subscription)
    assert summary["invoiced"] == 0
    assert subscription.status == before[0]
    assert subscription.plan_id == before[1]
    assert subscription.current_period_end == before[2]


async def test_run_cycle_endpoint_is_platform_scoped(client, admin_token, operator_token, platform_token):
    forbidden = await client.post(
        "/api/v1/platform/billing/run-cycle", headers=bearer(operator_token)
    )
    # 401 而非 403：租户 token 的 aud 是 admin，平台接口只认 aud=platform，JWT audience 校验直接判未认证。
    assert forbidden.status_code == 401

    allowed = await client.post("/api/v1/platform/billing/run-cycle", headers=bearer(platform_token))
    assert allowed.status_code == 200, allowed.text
    data = allowed.json()["data"]
    assert set(data) >= {"scanned", "invoiced", "renewed", "cancelled", "downgraded"}
