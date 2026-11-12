from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_context, get_db, require_permission
from app.core.response import ok, page_data
from app.models.notification_pref import TenantNotificationPref
from app.schemas.common import ApiResponse, PageData
from app.schemas.notification import (
    NotificationCreate,
    NotificationOut,
    NotificationStats,
)
from app.services import notification as notification_service
from app.services import notification_template as template_service
from app.services.auth import AuthContext

router = APIRouter(prefix="/notifications", tags=["触达通知"])


@router.get(
    "",
    response_model=ApiResponse[PageData[NotificationOut]],
    dependencies=[Depends(require_permission("notification:read"))],
)
async def list_notifications(
    current: int = Query(1, ge=1),
    pageSize: int = Query(10, ge=1, le=100),
    channel: str | None = None,
    status: str | None = None,
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    items, total = await notification_service.list_notifications(
        db, current, pageSize, channel, status, context.tenant.id
    )
    return ok(
        page_data(
            [NotificationOut.model_validate(item) for item in items], total, current, pageSize
        )
    )


@router.get(
    "/stats",
    response_model=ApiResponse[NotificationStats],
    dependencies=[Depends(require_permission("notification:read"))],
)
async def get_stats(
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    return ok(await notification_service.get_stats(db, context.tenant.id))


@router.post(
    "/send",
    response_model=ApiResponse[NotificationOut],
    dependencies=[Depends(require_permission("notification:send"))],
)
async def send_notification(
    payload: NotificationCreate,
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    record = await notification_service.send_notification(db, payload, context.tenant.id)
    return ok(NotificationOut.model_validate(record), "通知已进入发送流程")


@router.post(
    "/{notification_id}/retry",
    response_model=ApiResponse[NotificationOut],
    dependencies=[Depends(require_permission("notification:send"))],
)
async def retry_notification(
    notification_id: int,
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    record = await notification_service.retry_notification(db, notification_id, context.tenant.id)
    return ok(NotificationOut.model_validate(record), "通知已重试")


@router.get("/templates", response_model=ApiResponse[list[dict]])
async def list_available_templates(
    db: AsyncSession = Depends(get_db),
):
    """租户端只读：平台已启用的租户类模板。

    租户端不再提供「自己写模板并发通知」的能力（发送按钮已隐藏），
    这里只用于展示「有哪些通知会发给买家」。
    """
    rows = await template_service.list_templates(db, scope="tenant", only_enabled=True)
    return ok(
        [
            {
                "code": row.code,
                "name": row.name,
                "channel": row.channel,
                "subject": row.subject,
                "variables": row.variables,
                "mandatory": row.mandatory,
            }
            for row in rows
        ]
    )


# 站内信强制开启：欠费/安全/合规通知必须送达，不允许被关掉
MANDATORY_CHANNELS = {"inbox"}
OPTIONAL_CHANNELS = ["sms", "email"]


@router.get("/prefs", response_model=ApiResponse[dict])
async def get_prefs(
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    rows = list(
        (
            await db.scalars(
                select(TenantNotificationPref).where(
                    TenantNotificationPref.tenant_id == context.tenant.id
                )
            )
        ).all()
    )
    explicit = {row.channel: bool(row.enabled) for row in rows}
    return ok(
        {
            "channels": [
                {
                    "channel": channel,
                    "enabled": True,
                    "mandatory": True,
                }
                for channel in MANDATORY_CHANNELS
            ]
            + [
                {
                    "channel": channel,
                    "enabled": explicit.get(channel, True),
                    "mandatory": False,
                }
                for channel in OPTIONAL_CHANNELS
            ]
        }
    )


@router.put("/prefs", response_model=ApiResponse[dict])
async def save_prefs(
    payload: dict,
    _context=Depends(require_permission("notification:send")),
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    channel = str(payload.get("channel") or "")
    if channel in MANDATORY_CHANNELS:
        raise HTTPException(
            status_code=400,
            detail=f"{channel} 是强制渠道，不能关闭",
        )
    if channel not in OPTIONAL_CHANNELS:
        raise HTTPException(status_code=400, detail="不支持的渠道")

    row = (
        await db.scalars(
            select(TenantNotificationPref).where(
                TenantNotificationPref.tenant_id == context.tenant.id,
                TenantNotificationPref.channel == channel,
            )
        )
    ).first()
    if row is None:
        row = TenantNotificationPref(
            tenant_id=context.tenant.id, channel=channel, enabled=bool(payload.get("enabled", True))
        )
        db.add(row)
    else:
        row.enabled = bool(payload.get("enabled", True))
    await db.commit()
    return ok({"channel": channel, "enabled": row.enabled})
