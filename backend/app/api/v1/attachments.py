from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_context, get_db, require_permission
from app.core.response import ok, page_data
from app.schemas.attachment import AttachmentOut, AttachmentStats, SignedUrlOut
from app.schemas.common import ApiResponse, PageData
from app.services import attachment as attachment_service
from app.services.attachment import Viewer, primary_role
from app.services.auth import AuthContext

router = APIRouter(prefix="/attachments", tags=["附件管理"])

SIGNED_URL_TTL_SECONDS = 600


def _viewer(context: AuthContext) -> Viewer:
    return Viewer(
        user_id=context.user.id,
        role=primary_role(context.roles),
        tenant_id=context.tenant.id,
    )


@router.get("", response_model=ApiResponse[PageData[AttachmentOut]])
async def list_attachments(
    current: int = Query(1, ge=1),
    pageSize: int = Query(12, ge=1, le=100),
    category: str | None = None,
    keyword: str | None = None,
    source_role: str | None = None,
    review_status: str | None = None,
    recycle: bool = False,
    _context=Depends(require_permission("attachment:read")),
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    items, total = await attachment_service.list_for_tenant(
        db,
        context.tenant.id,
        current,
        pageSize,
        category=category,
        keyword=keyword,
        source_role=source_role,
        review_status=review_status,
        recycle=recycle,
    )
    viewer = _viewer(context)
    # 驳回/下架/软删各有各的可见规则，统一走 can_view，避免接口里各写一遍
    visible = [item for item in items if attachment_service.can_view(item, viewer)]
    return ok(
        page_data(
            [AttachmentOut.model_validate(item) for item in visible],
            total,
            current,
            pageSize,
        )
    )


@router.get("/stats", response_model=ApiResponse[AttachmentStats])
async def get_stats(
    _context=Depends(require_permission("attachment:read")),
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    return ok(await attachment_service.get_stats(db, context.tenant.id))


@router.post("/upload", response_model=ApiResponse[AttachmentOut])
async def upload_attachment(
    file: UploadFile = File(...),
    source_module: str = Form("manual"),
    _context=Depends(require_permission("attachment:upload")),
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    record = await attachment_service.save_upload(
        db,
        file,
        source_module=source_module,
        tenant_id=context.tenant.id,
        uploader=context.user.username,
        uploader_user_id=context.user.id,
        uploader_role=primary_role(context.roles),
        visibility="tenant",
    )
    return ok(AttachmentOut.model_validate(record), "附件上传成功")


@router.delete("/{attachment_id}", response_model=ApiResponse[None])
async def delete_attachment(
    attachment_id: int,
    _context=Depends(require_permission("attachment:delete")),
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    await attachment_service.soft_delete_attachment(
        db, attachment_id, context.tenant.id, context.user.id
    )
    return ok(None, "附件已移入回收站")


@router.post("/{attachment_id}/restore", response_model=ApiResponse[AttachmentOut])
async def restore_attachment(
    attachment_id: int,
    _context=Depends(require_permission("attachment:delete")),
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    record = await attachment_service.restore_attachment(db, attachment_id, context.tenant.id)
    return ok(AttachmentOut.model_validate(record), "附件已恢复")


@router.get("/{attachment_id}/download")
async def download_attachment(
    attachment_id: int,
    _context=Depends(require_permission("attachment:read")),
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    record = await attachment_service.get_visible_attachment(db, attachment_id, _viewer(context))
    path = attachment_service.disk_path(record)
    return FileResponse(
        path,
        media_type=record.mime_type,
        filename=record.original_name,
    )


@router.post("/{attachment_id}/signed-url", response_model=ApiResponse[SignedUrlOut])
async def signed_url(
    attachment_id: int,
    _context=Depends(require_permission("attachment:read")),
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    # 先校验可见性，再签名：签名 URL 不能成为绕过权限的通道
    await attachment_service.get_visible_attachment(db, attachment_id, _viewer(context))
    token = attachment_service.make_download_token(attachment_id, SIGNED_URL_TTL_SECONDS)
    return ok(
        SignedUrlOut(
            url=f"/api/v1/attachments/signed/{token}",
            expires_in=SIGNED_URL_TTL_SECONDS,
        )
    )


@router.get("/signed/{token}")
async def download_by_signature(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """给 <img src> 用的公开入口：靠短期签名放行，不需要 Authorization 头。"""
    record = await attachment_service.get_by_signed_token(db, token)
    path = attachment_service.disk_path(record)
    return FileResponse(path, media_type=record.mime_type)


@router.get("/public/{attachment_id}")
async def download_public(
    attachment_id: int,
    db: AsyncSession = Depends(get_db),
):
    """公开资源（店铺 logo、头像）的稳定直链，只放行 visibility=public 且未被下架/驳回的。"""
    record = await attachment_service.get_public_attachment(db, attachment_id)
    path = attachment_service.disk_path(record)
    return FileResponse(path, media_type=record.mime_type)
