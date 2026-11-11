from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_context, get_db, require_permission
from app.core.response import ok, page_data
from app.schemas.attachment import AttachmentOut, AttachmentStats
from app.schemas.common import ApiResponse, PageData
from app.services import attachment as attachment_service
from app.services.auth import AuthContext

router = APIRouter(prefix="/attachments", tags=["附件管理"])


@router.get(
    "",
    response_model=ApiResponse[PageData[AttachmentOut]],
    dependencies=[Depends(require_permission("attachment:read"))],
)
async def list_attachments(
    current: int = Query(1, ge=1),
    pageSize: int = Query(12, ge=1, le=100),
    category: str | None = None,
    keyword: str | None = None,
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    items, total = await attachment_service.list_attachments(
        db, current, pageSize, category, keyword, context.tenant.id
    )
    return ok(
        page_data([AttachmentOut.model_validate(item) for item in items], total, current, pageSize)
    )


@router.get(
    "/stats",
    response_model=ApiResponse[AttachmentStats],
    dependencies=[Depends(require_permission("attachment:read"))],
)
async def get_stats(
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    return ok(await attachment_service.get_stats(db, context.tenant.id))


@router.post(
    "/upload",
    response_model=ApiResponse[AttachmentOut],
    dependencies=[Depends(require_permission("attachment:upload"))],
)
async def upload_attachment(
    file: UploadFile = File(...),
    source_module: str = Form("manual"),
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    record = await attachment_service.save_upload(
        db, file, source_module, context.tenant.id, context.user.username
    )
    return ok(AttachmentOut.model_validate(record), "附件上传成功")


@router.delete(
    "/{attachment_id}",
    response_model=ApiResponse[None],
    dependencies=[Depends(require_permission("attachment:delete"))],
)
async def delete_attachment(
    attachment_id: int,
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    await attachment_service.delete_attachment(db, attachment_id, context.tenant.id)
    return ok(None, "附件已删除")
