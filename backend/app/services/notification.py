import asyncio
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dao import notification as notification_dao
from app.dao import setting as setting_dao
from app.models.notification import Notification
from app.schemas.notification import NotificationCreate, NotificationStats

AUDIENCE_SIZE = {
    "all": 1280,
    "role:admin": 12,
    "role:operator": 36,
    "role:viewer": 1232,
    "custom": 100,
}


async def list_notifications(
    db: AsyncSession,
    current: int,
    page_size: int,
    channel: str | None = None,
    status: str | None = None,
    tenant_id: int = 1,
) -> tuple[list[Notification], int]:
    return await notification_dao.list_notifications(
        db, current, page_size, channel, status, tenant_id
    )


async def send_notification(
    db: AsyncSession, payload: NotificationCreate, tenant_id: int = 1
) -> Notification:
    if payload.channel not in {"sms", "email", "inbox"}:
        raise HTTPException(status_code=400, detail="不支持的触达渠道")
    audience_size = AUDIENCE_SIZE.get(payload.audience, 100)
    now = datetime.now(UTC)

    channel_enabled = True
    if payload.channel in {"sms", "email"}:
        setting = await setting_dao.get_setting(db, payload.channel, tenant_id)
        channel_enabled = bool(setting and setting.enabled)

    status = "pending" if payload.scheduled_at and payload.scheduled_at > now else "sending"
    record = await notification_dao.create_notification(
        db,
        {
            "tenant_id": tenant_id,
            "title": payload.title,
            "channel": payload.channel,
            "template": payload.template,
            "audience": payload.audience,
            "content": payload.content,
            "status": status,
            "scheduled_at": payload.scheduled_at,
            "total": audience_size,
            "success_count": 0,
            "failed_count": 0,
        },
    )
    await db.commit()

    if status == "pending":
        await db.refresh(record)
        return record

    # Simulate an async delivery pipeline. Real implementation should enqueue a task
    # and update status via a worker / SSE channel.
    await asyncio.sleep(0.35)
    if channel_enabled:
        record.status = "success"
        record.success_count = audience_size
        record.failed_count = 0
        record.sent_at = datetime.now(UTC)
        record.error_message = None
    else:
        record.status = "failed"
        record.success_count = 0
        record.failed_count = audience_size
        record.error_message = f"{payload.channel} 渠道未启用"
    await db.commit()
    await db.refresh(record)
    return record


async def retry_notification(
    db: AsyncSession, notification_id: int, tenant_id: int = 1
) -> Notification:
    record = await notification_dao.get_notification(db, notification_id, tenant_id)
    if record is None:
        raise HTTPException(status_code=404, detail="通知记录不存在")
    if record.status == "success":
        return record
    record.status = "success"
    record.success_count = record.total
    record.failed_count = 0
    record.sent_at = datetime.now(UTC)
    record.error_message = None
    await db.commit()
    await db.refresh(record)
    return record


async def get_stats(db: AsyncSession, tenant_id: int = 1) -> NotificationStats:
    return NotificationStats(**await notification_dao.notification_stats(db, tenant_id))
