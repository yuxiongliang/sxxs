"""平台端内容审核控制台。只接受 aud=platform 的 token。

平台在这里只做两件事：**出审核结论**、**强制下架**。
附件的日常管理（上传/删除/回收站）属于租户，不在这里。
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_platform_permission
from app.core.response import ok, page_data
from app.dao import attachment as attachment_dao
from app.models.attachment import Attachment
from app.models.moderation import ModerationLog
from app.models.tenant import Tenant
from app.schemas.attachment import (
    ModerationDecisionIn,
    ModerationQueueStats,
    PlatformAttachmentOut,
)
from app.schemas.common import ApiResponse, PageData
from app.services import attachment as attachment_service
from app.services import moderation
from app.services.platform_auth import PlatformContext

router = APIRouter(prefix="/platform/moderation", tags=["平台内容审核"])

VIEW = "platform:attachment:view"
REVIEW = "platform:attachment:review"
TAKEDOWN = "platform:attachment:takedown"


async def _tenant_names(db: AsyncSession, items: list[Attachment]) -> dict[int, str]:
    ids = {item.tenant_id for item in items if item.tenant_id is not None}
    if not ids:
        return {}
    rows = (await db.execute(select(Tenant.id, Tenant.name).where(Tenant.id.in_(ids)))).all()
    return {int(row[0]): str(row[1]) for row in rows}


def _serialize(item: Attachment, names: dict[int, str]) -> PlatformAttachmentOut:
    data = PlatformAttachmentOut.model_validate(item)
    if item.tenant_id is not None:
        data.tenant_name = names.get(item.tenant_id)
    return data


@router.get("/queue", response_model=ApiResponse[PageData[PlatformAttachmentOut]])
async def moderation_queue(
    current: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    review_status: str = Query("pending"),
    tenant_id: int | None = None,
    source_role: str | None = None,
    keyword: str | None = None,
    only_takedown: bool = False,
    _context=Depends(require_platform_permission(VIEW)),
    db: AsyncSession = Depends(get_db),
):
    items, total = await attachment_service.list_for_platform(
        db,
        current,
        pageSize,
        tenant_id=tenant_id,
        review_status=review_status,
        source_role=source_role,
        keyword=keyword,
        only_takedown=only_takedown,
    )
    names = await _tenant_names(db, items)
    return ok(page_data([_serialize(item, names) for item in items], total, current, pageSize))


@router.get("/stats", response_model=ApiResponse[ModerationQueueStats])
async def moderation_stats(
    _context=Depends(require_platform_permission(VIEW)),
    db: AsyncSession = Depends(get_db),
):
    counts = await attachment_dao.count_by_review_status(db)
    takedown = await attachment_dao.count_takedown(db)
    return ok(
        ModerationQueueStats(
            pending=counts.get(moderation.PENDING, 0),
            manual=counts.get(moderation.MANUAL, 0),
            failed=counts.get(moderation.FAILED, 0),
            rejected=counts.get(moderation.REJECTED, 0),
            approved=counts.get(moderation.APPROVED, 0),
            takedown=takedown,
        )
    )


@router.post("/{attachment_id}/review", response_model=ApiResponse[PlatformAttachmentOut])
async def review_attachment(
    attachment_id: int,
    payload: ModerationDecisionIn,
    context: PlatformContext = Depends(require_platform_permission(REVIEW)),
    db: AsyncSession = Depends(get_db),
):
    record = await db.get(Attachment, attachment_id)
    if record is None:
        raise HTTPException(status_code=404, detail="附件不存在")
    if payload.decision not in {moderation.APPROVED, moderation.REJECTED}:
        raise HTTPException(status_code=400, detail="结论只能是 approved / rejected")
    await moderation.manual_review(
        db, record, payload.decision, context.user.id, payload.categories
    )
    await db.refresh(record)
    names = await _tenant_names(db, [record])
    return ok(_serialize(record, names), "审核结论已保存")


@router.post("/{attachment_id}/takedown", response_model=ApiResponse[PlatformAttachmentOut])
async def takedown_attachment(
    attachment_id: int,
    _context=Depends(require_platform_permission(TAKEDOWN)),
    db: AsyncSession = Depends(get_db),
):
    record = await db.get(Attachment, attachment_id)
    if record is None:
        raise HTTPException(status_code=404, detail="附件不存在")
    record.admin_hidden = True
    await db.commit()
    await db.refresh(record)
    names = await _tenant_names(db, [record])
    return ok(_serialize(record, names), "已强制下架")


@router.post("/{attachment_id}/restore", response_model=ApiResponse[PlatformAttachmentOut])
async def restore_attachment(
    attachment_id: int,
    _context=Depends(require_platform_permission(TAKEDOWN)),
    db: AsyncSession = Depends(get_db),
):
    record = await db.get(Attachment, attachment_id)
    if record is None:
        raise HTTPException(status_code=404, detail="附件不存在")
    record.admin_hidden = False
    await db.commit()
    await db.refresh(record)
    names = await _tenant_names(db, [record])
    return ok(_serialize(record, names), "已解除下架")


@router.get("/{attachment_id}/download")
async def download_attachment(
    attachment_id: int,
    _context=Depends(require_platform_permission(VIEW)),
    db: AsyncSession = Depends(get_db),
):
    record = await db.get(Attachment, attachment_id)
    if record is None:
        raise HTTPException(status_code=404, detail="附件不存在")
    path = attachment_service.disk_path(record)
    return FileResponse(path, media_type=record.mime_type, filename=record.original_name)


@router.get("/{attachment_id}/logs", response_model=ApiResponse[list[dict]])
async def moderation_logs(
    attachment_id: int,
    _context=Depends(require_platform_permission(VIEW)),
    db: AsyncSession = Depends(get_db),
):
    rows = list(
        (
            await db.scalars(
                select(ModerationLog)
                .where(ModerationLog.attachment_id == attachment_id)
                .order_by(ModerationLog.id.desc())
                .limit(50)
            )
        ).all()
    )
    return ok(
        [
            {
                "id": row.id,
                "provider": row.provider,
                "decision": row.decision,
                "categories": row.categories,
                "confidence": row.confidence,
                "elapsed_ms": row.elapsed_ms,
                "source": row.source,
                "reviewer_id": row.reviewer_id,
                "created_at": row.created_at,
            }
            for row in rows
        ]
    )
