"""Audit trail for the order / payment / settlement chain.

Design rules:

* **Same transaction as the change.** ``record()`` only stages an ``AuditLog`` row;
  the caller's ``commit()`` persists it together with the business change, so an
  audited mutation can never commit without its audit row (or vice versa).
* **Tenant scoped.** Every row carries ``tenant_id``; reads are filtered by the
  caller's tenant and only a platform-wide role may look across tenants.
* **Append only.** There is no update/delete helper — the trail is immutable.
"""

from __future__ import annotations

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.request_context import get_request_meta
from app.models.audit import AuditLog
from app.services.auth import AuthContext

logger = structlog.get_logger(__name__)

# Centralised action names so the trail stays queryable and greppable.
ACTION_ORDER_CREATED = "order.created"
ACTION_ORDER_PAID = "order.paid"
ACTION_ORDER_CANCELLED = "order.cancelled"
ACTION_ORDER_CONFIRMED = "order.confirmed"
ACTION_SELLER_ORDER_SHIPPED = "seller_order.shipped"
ACTION_SELLER_ORDER_REFUNDED = "seller_order.refunded"
ACTION_SELLER_APPLIED = "seller.applied"
ACTION_SELLER_APPROVED = "seller.approved"
ACTION_PRODUCT_CREATED = "product.created"
ACTION_PRODUCT_REVIEWED = "product.reviewed"
ACTION_PAYOUT_REQUESTED = "payout.requested"
ACTION_PAYOUT_APPROVED = "payout.approved"
ACTION_PAYOUT_REJECTED = "payout.rejected"
ACTION_PAYOUT_PAID = "payout.paid"
ACTION_SETTLEMENT_CREATED = "settlement_batch.created"
ACTION_SETTLEMENT_CONFIRMED = "settlement_batch.confirmed"
ACTION_SETTLEMENT_PAID = "settlement_batch.paid"
ACTION_COMMISSION_RULE_CREATED = "commission_rule.created"
ACTION_COMMISSION_RULE_UPDATED = "commission_rule.updated"
ACTION_COMMISSION_RULE_DELETED = "commission_rule.deleted"
ACTION_IM_MESSAGE_MODERATED = "im.message.moderated"
ACTION_TENANT_SUSPENDED = "tenant.suspended"
ACTION_TENANT_RESUMED = "tenant.resumed"
ACTION_TENANT_UPDATED = "tenant.updated"
ACTION_ROLE_PERMISSIONS_UPDATED = "role.permissions_updated"
ACTION_USER_ROLE_CHANGED = "user.role_changed"
ACTION_SUBSCRIPTION_RENEWED = "subscription.renewed"
ACTION_SUBSCRIPTION_PAST_DUE = "subscription.past_due"
ACTION_SUBSCRIPTION_CANCELLED = "subscription.cancelled"
ACTION_SUBSCRIPTION_DOWNGRADED = "subscription.downgraded"


async def record(
    db: AsyncSession,
    *,
    action: str,
    tenant_id: int | None = None,
    actor_id: int | None = None,
    target_type: str = "",
    target_id: str | int | None = "",
    before: dict | None = None,
    after: dict | None = None,
) -> AuditLog:
    """Stage an audit row on the current session (committed by the caller)."""
    meta = get_request_meta()
    entry = AuditLog(
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else "",
        before=before,
        after=after,
        ip=meta.ip or None,
        trace_id=meta.trace_id or None,
    )
    db.add(entry)
    await db.flush()
    return entry


def is_platform_viewer(context: AuthContext) -> bool:
    """Platform-wide read access.

    Checked by *permission* rather than role name: the demo superuser holds the
    legacy ``admin`` role (not ``platform_admin``) yet must be able to audit
    across tenants.
    """
    return "platform_admin" in context.roles or "platform:tenant:read" in context.permissions


async def list_logs(
    db: AsyncSession,
    context: AuthContext,
    *,
    current: int = 1,
    page_size: int = 20,
    action: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    actor_id: int | None = None,
    tenant_id: int | None = None,
) -> tuple[list[AuditLog], int]:
    """Query the trail. A tenant only ever sees its own rows."""
    stmt = select(AuditLog)
    count_stmt = select(func.count(AuditLog.id))

    if not is_platform_viewer(context):
        stmt = stmt.where(AuditLog.tenant_id == context.tenant.id)
        count_stmt = count_stmt.where(AuditLog.tenant_id == context.tenant.id)
    elif tenant_id is not None:
        stmt = stmt.where(AuditLog.tenant_id == tenant_id)
        count_stmt = count_stmt.where(AuditLog.tenant_id == tenant_id)

    if action:
        stmt = stmt.where(AuditLog.action == action)
        count_stmt = count_stmt.where(AuditLog.action == action)
    if target_type:
        stmt = stmt.where(AuditLog.target_type == target_type)
        count_stmt = count_stmt.where(AuditLog.target_type == target_type)
    if target_id:
        stmt = stmt.where(AuditLog.target_id == str(target_id))
        count_stmt = count_stmt.where(AuditLog.target_id == str(target_id))
    if actor_id is not None:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
        count_stmt = count_stmt.where(AuditLog.actor_id == actor_id)

    total = int(await db.scalar(count_stmt) or 0)
    rows = list(
        (
            await db.scalars(
                stmt.order_by(AuditLog.id.desc()).offset((current - 1) * page_size).limit(page_size)
            )
        ).all()
    )
    return rows, total


async def distinct_actions(db: AsyncSession, context: AuthContext) -> list[str]:
    stmt = select(AuditLog.action).distinct()
    if not is_platform_viewer(context):
        stmt = stmt.where(AuditLog.tenant_id == context.tenant.id)
    return sorted(row for row in (await db.scalars(stmt)).all() if row)


async def record_platform(
    db: AsyncSession,
    *,
    actor_id: int | None,
    action: str,
    target_type: str = "",
    target_id: str = "",
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    """记录一条平台级审计。

    用 `tenant_id IS NULL` 表示平台操作 —— 这样不需要新增列，
    而租户侧查询永远带 tenant_id 过滤，天然看不到平台行。
    """
    db.add(
        AuditLog(
            tenant_id=None,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=str(target_id),
            before=before,
            after=after,
        )
    )
    await db.flush()


async def list_platform_logs(
    db: AsyncSession, current: int = 1, page_size: int = 20
) -> tuple[list[AuditLog], int]:
    """平台审计：只看 tenant_id 为空的行。"""
    stmt = select(AuditLog).where(AuditLog.tenant_id.is_(None))
    count_stmt = select(func.count(AuditLog.id)).where(AuditLog.tenant_id.is_(None))
    total = int(await db.scalar(count_stmt) or 0)
    stmt = stmt.order_by(AuditLog.id.desc()).offset((current - 1) * page_size).limit(page_size)
    return list((await db.scalars(stmt)).all()), total
