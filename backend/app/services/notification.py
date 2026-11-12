import asyncio
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dao import notification as notification_dao
from app.models.notification import Notification
from app.models.notification_template import NotificationTemplate
from app.models.tenant import Tenant
from app.schemas.notification import NotificationCreate, NotificationStats
from app.services import notification_template as template_service
from app.services import setting_resolver

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
        # 走 resolver：跟随系统的租户要用**平台**的启用状态，
        # 直接读 system_settings 拿不到继承后的结果。
        resolved = await setting_resolver.resolve(db, tenant_id, payload.channel)
        channel_enabled = bool(resolved.enabled)

    title = payload.title
    content = payload.content
    if payload.template:
        template = (
            await db.scalars(
                select(NotificationTemplate).where(
                    NotificationTemplate.scope == "tenant",
                    NotificationTemplate.code == payload.template,
                    NotificationTemplate.enabled.is_(True),
                )
            )
        ).first()
        if template is None:
            raise HTTPException(
                status_code=400,
                detail=f"通知模板不存在或已停用：{payload.template}",
            )
        tenant = await db.get(Tenant, tenant_id)
        tenant_name = (tenant.display_name or tenant.name) if tenant else ""
        context = {
            "tenant_name": tenant_name,
            "tenant_short_name": tenant_name,
            "tenant_domain": "",  # B6（自定义域名）上线后填真实域名
            "buyer_name": payload.audience or "",
            "order_no": "",
            "amount": "",
            "site_url": "",
            "support_email": "",
        }
        # 渲染会校验变量：缺失直接 400，不会把 {{...}} 原样发出去
        content = template_service.render(template.body, context)
        if template.subject:
            title = template_service.render(template.subject, context)

    status = "pending" if payload.scheduled_at and payload.scheduled_at > now else "sending"
    record = await notification_dao.create_notification(
        db,
        {
            "tenant_id": tenant_id,
            "title": title,
            "channel": payload.channel,
            "template": payload.template,
            "audience": payload.audience,
            "content": content,
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
