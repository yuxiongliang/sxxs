from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification


async def list_notifications(
    db: AsyncSession,
    current: int,
    page_size: int,
    channel: str | None = None,
    status: str | None = None,
    tenant_id: int = 1,
) -> tuple[list[Notification], int]:
    conditions = [Notification.tenant_id == tenant_id]
    if channel and channel != "all":
        conditions.append(Notification.channel == channel)
    if status and status != "all":
        conditions.append(Notification.status == status)

    count_stmt = select(func.count(Notification.id))
    stmt = select(Notification)
    if conditions:
        count_stmt = count_stmt.where(*conditions)
        stmt = stmt.where(*conditions)

    total = await db.scalar(count_stmt) or 0
    stmt = stmt.order_by(Notification.id.desc()).offset((current - 1) * page_size).limit(page_size)
    items = list((await db.scalars(stmt)).all())
    return items, total


async def get_notification(
    db: AsyncSession, notification_id: int, tenant_id: int = 1
) -> Notification | None:
    result = await db.scalars(
        select(Notification).where(
            Notification.id == notification_id, Notification.tenant_id == tenant_id
        )
    )
    return result.first()


async def create_notification(db: AsyncSession, data: dict) -> Notification:
    notification = Notification(**data)
    db.add(notification)
    await db.flush()
    await db.refresh(notification)
    return notification


async def notification_stats(db: AsyncSession, tenant_id: int = 1) -> dict:
    status_rows = []
    status_stmt = (
        select(Notification.status, func.count(Notification.id))
        .where(Notification.tenant_id == tenant_id)
        .group_by(Notification.status)
    )
    async for row in await db.stream(status_stmt):
        status_rows.append((row[0], row[1]))
    channel_rows = []
    channel_stmt = (
        select(Notification.channel, func.count(Notification.id))
        .where(Notification.tenant_id == tenant_id)
        .group_by(Notification.channel)
    )
    async for row in await db.stream(channel_stmt):
        channel_rows.append((row[0], row[1]))
    status_counts = {row[0]: row[1] for row in status_rows}
    return {
        "total": sum(status_counts.values()),
        "success": status_counts.get("success", 0),
        "failed": status_counts.get("failed", 0),
        "pending": status_counts.get("pending", 0),
        "channels": {row[0]: row[1] for row in channel_rows},
    }
