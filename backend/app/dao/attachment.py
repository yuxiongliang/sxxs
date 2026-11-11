from sqlalchemy import bindparam, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attachment import Attachment


async def list_attachments(
    db: AsyncSession,
    current: int,
    page_size: int,
    category: str | None = None,
    keyword: str | None = None,
    tenant_id: int = 1,
) -> tuple[list[Attachment], int]:
    conditions = [Attachment.tenant_id == tenant_id]
    if category and category != "all":
        conditions.append(Attachment.category == category)
    if keyword:
        like = bindparam("keyword_pattern", f"%{keyword}%")
        conditions.append(
            or_(
                Attachment.name.ilike(like),
                Attachment.original_name.ilike(like),
                Attachment.source_module.ilike(like),
            )
        )

    count_stmt = select(func.count(Attachment.id))
    stmt = select(Attachment)
    if conditions:
        count_stmt = count_stmt.where(*conditions)
        stmt = stmt.where(*conditions)

    total = await db.scalar(count_stmt) or 0
    stmt = stmt.order_by(Attachment.id.desc()).offset((current - 1) * page_size).limit(page_size)
    items = list((await db.scalars(stmt)).all())
    return items, total


async def get_attachment(
    db: AsyncSession, attachment_id: int, tenant_id: int = 1
) -> Attachment | None:
    result = await db.scalars(
        select(Attachment).where(Attachment.id == attachment_id, Attachment.tenant_id == tenant_id)
    )
    return result.first()


async def create_attachment(db: AsyncSession, data: dict) -> Attachment:
    attachment = Attachment(**data)
    db.add(attachment)
    await db.flush()
    await db.refresh(attachment)
    return attachment


async def delete_attachment(db: AsyncSession, attachment: Attachment) -> None:
    await db.delete(attachment)


async def attachment_stats(db: AsyncSession, tenant_id: int = 1) -> dict:
    stmt = (
        select(
            Attachment.category,
            func.count(Attachment.id),
            func.coalesce(func.sum(Attachment.size), 0),
        )
        .where(Attachment.tenant_id == tenant_id)
        .group_by(Attachment.category)
    )
    rows = []
    async for row in await db.stream(stmt):
        rows.append((row[0], row[1], row[2]))
    counts = {row[0]: row[1] for row in rows}
    total_size = await db.scalar(
        select(func.coalesce(func.sum(Attachment.size), 0)).where(Attachment.tenant_id == tenant_id)
    )
    try:
        total_size_value = int(total_size or 0)
    except (TypeError, ValueError):
        total_size_value = 0
    return {
        "total": sum(counts.values()),
        "images": counts.get("image", 0),
        "videos": counts.get("video", 0),
        "documents": counts.get("document", 0),
        "others": counts.get("other", 0),
        "totalSize": total_size_value,
    }
