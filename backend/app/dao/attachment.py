from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import bindparam, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attachment import Attachment


@dataclass
class AttachmentQuery:
    """附件查询条件。

    租户端：`tenant_id` 必填，默认排除软删（回收站用 `recycle=True`）。
    平台端：`all_tenants=True`，可按租户过滤，也可跨租户看回收站。
    """

    tenant_id: int | None = None
    all_tenants: bool = False
    category: str | None = None
    keyword: str | None = None
    source_role: str | None = None
    review_status: str | None = None
    visibility: str | None = None
    recycle: bool = False
    include_deleted: bool = False


def _conditions(query: AttachmentQuery) -> list:
    conditions = []
    if not query.all_tenants:
        if query.tenant_id is None:
            conditions.append(Attachment.tenant_id.is_(None))
        else:
            conditions.append(Attachment.tenant_id == query.tenant_id)
    elif query.tenant_id is not None:
        conditions.append(Attachment.tenant_id == query.tenant_id)

    if query.recycle:
        conditions.append(Attachment.deleted_at.is_not(None))
    elif not query.include_deleted:
        conditions.append(Attachment.deleted_at.is_(None))

    if query.category and query.category != "all":
        conditions.append(Attachment.category == query.category)
    if query.source_role:
        conditions.append(Attachment.uploader_role == query.source_role)
    if query.review_status and query.review_status != "all":
        conditions.append(Attachment.review_status == query.review_status)
    if query.visibility:
        conditions.append(Attachment.visibility == query.visibility)
    if query.keyword:
        like = bindparam("keyword_pattern", f"%{query.keyword}%")
        conditions.append(
            or_(
                Attachment.name.ilike(like),
                Attachment.original_name.ilike(like),
                Attachment.source_module.ilike(like),
            )
        )
    return conditions


async def list_attachments(
    db: AsyncSession, current: int, page_size: int, query: AttachmentQuery
) -> tuple[list[Attachment], int]:
    conditions = _conditions(query)
    count_stmt = select(func.count(Attachment.id)).where(*conditions)
    stmt = select(Attachment).where(*conditions)
    total = await db.scalar(count_stmt) or 0
    stmt = stmt.order_by(Attachment.id.desc()).offset((current - 1) * page_size).limit(page_size)
    items = list((await db.scalars(stmt)).all())
    return items, total


async def get_attachment(db: AsyncSession, attachment_id: int) -> Attachment | None:
    return await db.get(Attachment, attachment_id)


async def get_tenant_attachment(
    db: AsyncSession, attachment_id: int, tenant_id: int | None
) -> Attachment | None:
    stmt = select(Attachment).where(Attachment.id == attachment_id)
    if tenant_id is None:
        stmt = stmt.where(Attachment.tenant_id.is_(None))
    else:
        stmt = stmt.where(Attachment.tenant_id == tenant_id)
    return (await db.scalars(stmt)).first()


async def create_attachment(db: AsyncSession, data: dict) -> Attachment:
    attachment = Attachment(**data)
    db.add(attachment)
    await db.flush()
    await db.refresh(attachment)
    return attachment


async def soft_delete(db: AsyncSession, attachment: Attachment, user_id: int | None) -> None:
    """租户软删：业务上不再出现，但平台审核/取证仍能看到这条记录。"""
    attachment.deleted_at = datetime.now(UTC)
    attachment.deleted_by = user_id


async def restore(db: AsyncSession, attachment: Attachment) -> None:
    attachment.deleted_at = None
    attachment.deleted_by = None


async def attachment_stats(db: AsyncSession, tenant_id: int | None) -> dict:
    # 不拼可变列表：列表元素类型推断会把 BinaryExpression 与 ColumnElement 弄混
    tenant_filter = (
        Attachment.tenant_id.is_(None) if tenant_id is None else Attachment.tenant_id == tenant_id
    )
    conditions = (Attachment.deleted_at.is_(None), tenant_filter)
    stmt = (
        select(
            Attachment.category,
            func.count(Attachment.id),
            func.coalesce(func.sum(Attachment.size), 0),
        )
        .where(*conditions)
        .group_by(Attachment.category)
    )
    counts: dict[str, int] = {}
    async for row in await db.stream(stmt):
        counts[str(row[0])] = int(row[1])
    total_size = await db.scalar(
        select(func.coalesce(func.sum(Attachment.size), 0)).where(*conditions)
    )
    return {
        "total": sum(counts.values()),
        "images": counts.get("image", 0),
        "videos": counts.get("video", 0),
        "documents": counts.get("document", 0),
        "others": counts.get("other", 0),
        "totalSize": int(total_size or 0),
    }


async def count_by_review_status(db: AsyncSession, tenant_id: int | None = None) -> dict[str, int]:
    """审核队列计数（平台用）。只统计未软删的。"""
    stmt = select(Attachment.review_status, func.count(Attachment.id)).where(
        Attachment.deleted_at.is_(None),
    )
    if tenant_id is not None:
        stmt = stmt.where(Attachment.tenant_id == tenant_id)
    stmt = stmt.group_by(Attachment.review_status)
    result: dict[str, int] = {}
    async for row in await db.stream(stmt):
        result[str(row[0])] = int(row[1])
    return result


async def count_takedown(db: AsyncSession) -> int:
    return int(
        await db.scalar(
            select(func.count(Attachment.id)).where(
                Attachment.admin_hidden.is_(True),
                Attachment.deleted_at.is_(None),
            )
        )
        or 0
    )
