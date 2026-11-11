"""Audit trail read API (`audit:read`)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_context, get_db, require_permission
from app.core.response import ok, page_data
from app.schemas.common import ApiResponse
from app.services import audit as audit_service
from app.services.auth import AuthContext

router = APIRouter(prefix="/audit-logs", tags=["审计日志"])


@router.get(
    "",
    response_model=ApiResponse[dict],
    dependencies=[Depends(require_permission("audit:read"))],
)
async def list_audit_logs(
    current: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    action: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    actor_id: int | None = None,
    tenant_id: int | None = None,
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await audit_service.list_logs(
        db,
        context,
        current=current,
        page_size=pageSize,
        action=action,
        target_type=target_type,
        target_id=target_id,
        actor_id=actor_id,
        tenant_id=tenant_id,
    )
    items = [
        {
            "id": row.id,
            "tenant_id": row.tenant_id,
            "actor_id": row.actor_id,
            "action": row.action,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "before": row.before,
            "after": row.after,
            "ip": row.ip,
            "trace_id": row.trace_id,
            "created_at": row.created_at,
        }
        for row in rows
    ]
    return ok(page_data(items, total, current, pageSize))


@router.get(
    "/actions",
    response_model=ApiResponse[list[str]],
    dependencies=[Depends(require_permission("audit:read"))],
)
async def list_audit_actions(
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    return ok(await audit_service.distinct_actions(db, context))
