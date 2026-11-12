"""附件服务。

三权分离（任何一方都不能覆盖另一方）：
  * 审核结论 / 强制下架 —— 只有平台（见 services/moderation）
  * 软删 / 恢复          —— 只有租户

下载鉴权：生产环境不再直出 /uploads，一律走 `get_visible_attachment` 校验
（租户 + visibility + 审核状态 + 是否被下架）。图片展示用签名 URL，避免裂图。
"""

import hashlib
import mimetypes
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.dao import attachment as attachment_dao
from app.dao.attachment import AttachmentQuery
from app.models.attachment import Attachment
from app.schemas.attachment import AttachmentStats
from app.services import moderation

ADMIN_ROLES = {"admin", "tenant_admin", "tenant_owner", "platform_admin"}
DOWNLOAD_AUDIENCE = "attachment-download"


def primary_role(roles: list[str]) -> str:
    """把角色集合归一成上传/可见性判定用的三个粗粒度身份。

    租户里一个用户可能同时是 admin 与 seller，判定时**取最高权限**，
    否则管理员上传的附件会被误判成卖家私有。
    """
    if any(role in ADMIN_ROLES for role in roles):
        return "admin"
    if any(role.startswith("seller") for role in roles):
        return "seller"
    if "customer" in roles:
        return "buyer"
    return "viewer"


def _category_for(mime_type: str, extension: str) -> str:
    major = mime_type.split("/", 1)[0]
    if major in {"image", "video", "audio"}:
        return "image" if major == "image" else ("video" if major == "video" else "other")
    if mime_type in {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/plain",
        "text/markdown",
        "application/json",
    } or extension in {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".txt", ".md", ".json", ".csv"}:
        return "document"
    return "other"


@dataclass
class Viewer:
    """谁在看这个附件。platform 视图优先于一切租户判定。"""

    user_id: int | None
    role: str
    tenant_id: int | None
    is_platform: bool = False


def can_view(attachment: Attachment, viewer: Viewer) -> bool:
    """可见性矩阵的**唯一**实现。改规则只改这里，别在接口里各写一遍。"""
    if viewer.is_platform:
        return True
    # 强制下架：对平台以外所有人立即隐藏
    if attachment.admin_hidden:
        return False

    is_uploader = viewer.user_id is not None and attachment.uploader_user_id == viewer.user_id
    same_tenant_admin = (
        viewer.tenant_id is not None
        and viewer.tenant_id == attachment.tenant_id
        and viewer.role in ADMIN_ROLES
    )

    # 软删：只有同租户管理员能在回收站里看到
    if attachment.deleted_at is not None:
        return same_tenant_admin

    # 驳回：上传者本人 + 同租户管理员可见（取证），其他人一律不可见
    if attachment.review_status == moderation.REJECTED:
        return is_uploader or same_tenant_admin

    if attachment.visibility == "public":
        return True

    if viewer.tenant_id is None or viewer.tenant_id != attachment.tenant_id:
        return False

    if attachment.visibility == "tenant":
        return True
    if attachment.visibility == "seller":
        return is_uploader or viewer.role.startswith("seller") or same_tenant_admin
    if attachment.visibility == "buyer":
        return is_uploader or same_tenant_admin
    return False


def _download_secret() -> str:
    # 派生密钥：下载签名即使泄露，也不能被当成 access token 重放
    return f"{settings.jwt_secret}:{DOWNLOAD_AUDIENCE}"


def make_download_token(attachment_id: int, expires_seconds: int = 600) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(attachment_id),
        "aud": DOWNLOAD_AUDIENCE,
        "iat": now,
        "exp": now + timedelta(seconds=expires_seconds),
    }
    return jwt.encode(payload, _download_secret(), algorithm=settings.jwt_algorithm)


def decode_download_token(token: str) -> int | None:
    try:
        payload = jwt.decode(
            token,
            _download_secret(),
            algorithms=[settings.jwt_algorithm],
            audience=DOWNLOAD_AUDIENCE,
        )
    except jwt.PyJWTError:
        return None
    try:
        return int(payload.get("sub", 0))
    except (TypeError, ValueError):
        return None


def verify_download_token(token: str, attachment_id: int) -> bool:
    return decode_download_token(token) == attachment_id


async def get_by_signed_token(db: AsyncSession, token: str) -> Attachment:
    """签名 URL 兑换。下架/驳回的即使签名有效也不能下载。"""
    attachment_id = decode_download_token(token)
    if attachment_id is None:
        raise HTTPException(status_code=404, detail="链接已失效")
    record = await attachment_dao.get_attachment(db, attachment_id)
    if record is None or record.admin_hidden or record.review_status == moderation.REJECTED:
        raise HTTPException(status_code=404, detail="附件不存在")
    return record


async def get_public_attachment(db: AsyncSession, attachment_id: int) -> Attachment:
    """公开资源（logo/头像）稳定直链：只放行 visibility=public 且未下架/未驳回/未软删的。"""
    record = await attachment_dao.get_attachment(db, attachment_id)
    if (
        record is None
        or record.visibility != "public"
        or record.admin_hidden
        or record.deleted_at is not None
        or record.review_status == moderation.REJECTED
    ):
        raise HTTPException(status_code=404, detail="附件不存在")
    return record


async def save_upload(
    db: AsyncSession,
    file: UploadFile,
    *,
    source_module: str,
    tenant_id: int | None,
    uploader: str,
    uploader_user_id: int | None,
    uploader_role: str = "admin",
    visibility: str = "tenant",
) -> Attachment:
    original_name = Path(file.filename or "unnamed").name
    extension = Path(original_name).suffix.lower()
    mime_type = (
        file.content_type or mimetypes.guess_type(original_name)[0] or "application/octet-stream"
    )
    stored_name = f"{uuid.uuid4().hex}{extension}"
    target = settings.upload_path / stored_name

    size = 0
    checksum = hashlib.sha256()
    try:
        with target.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_upload_size:
                    raise HTTPException(status_code=413, detail="文件超过大小限制")
                checksum.update(chunk)
                out.write(chunk)
    except HTTPException:
        target.unlink(missing_ok=True)
        raise
    except OSError as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"文件保存失败：{exc}") from exc

    if size == 0:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="不能上传空文件")

    url = f"{settings.public_base_url.rstrip('/')}/uploads/{stored_name}"
    record = await attachment_dao.create_attachment(
        db,
        {
            "tenant_id": tenant_id,
            "name": original_name,
            "original_name": original_name,
            "mime_type": mime_type,
            "size": size,
            "extension": extension,
            "category": _category_for(mime_type, extension),
            "storage": "local",
            "storage_key": stored_name,
            "url": url,
            "uploader": uploader,
            "uploader_user_id": uploader_user_id,
            "uploader_role": uploader_role,
            "source_module": source_module or "manual",
            "visibility": visibility,
            "checksum": checksum.hexdigest(),
        },
    )
    await db.commit()
    await db.refresh(record)
    # 上传即刻进审核管道（异步；无 worker 时就地审完，保证数据一致）
    await moderation.submit(db, record)
    await db.commit()
    await db.refresh(record)
    return record


async def list_for_tenant(
    db: AsyncSession,
    tenant_id: int | None,
    current: int,
    page_size: int,
    *,
    category: str | None = None,
    keyword: str | None = None,
    source_role: str | None = None,
    review_status: str | None = None,
    recycle: bool = False,
) -> tuple[list[Attachment], int]:
    query = AttachmentQuery(
        tenant_id=tenant_id,
        category=category,
        keyword=keyword,
        source_role=source_role,
        review_status=review_status,
        recycle=recycle,
    )
    return await attachment_dao.list_attachments(db, current, page_size, query)


async def list_for_platform(
    db: AsyncSession,
    current: int,
    page_size: int,
    *,
    tenant_id: int | None = None,
    category: str | None = None,
    keyword: str | None = None,
    source_role: str | None = None,
    review_status: str | None = None,
    only_takedown: bool = False,
) -> tuple[list[Attachment], int]:
    query = AttachmentQuery(
        tenant_id=tenant_id,
        all_tenants=True,
        category=category,
        keyword=keyword,
        source_role=source_role,
        review_status=review_status,
        include_deleted=True,
    )
    items, total = await attachment_dao.list_attachments(db, current, page_size, query)
    if only_takedown:
        items = [item for item in items if item.admin_hidden]
        total = len(items)
    return items, total


async def get_visible_attachment(
    db: AsyncSession, attachment_id: int, viewer: Viewer
) -> Attachment:
    record = await attachment_dao.get_attachment(db, attachment_id)
    # 不存在与不可见都返回 404，避免被用来探测附件是否存在
    if record is None or not can_view(record, viewer):
        raise HTTPException(status_code=404, detail="附件不存在")
    return record


async def soft_delete_attachment(
    db: AsyncSession, attachment_id: int, tenant_id: int | None, user_id: int | None
) -> None:
    record = await attachment_dao.get_tenant_attachment(db, attachment_id, tenant_id)
    if record is None or record.deleted_at is not None:
        raise HTTPException(status_code=404, detail="附件不存在")
    await attachment_dao.soft_delete(db, record, user_id)
    await db.commit()


async def restore_attachment(
    db: AsyncSession, attachment_id: int, tenant_id: int | None
) -> Attachment:
    record = await attachment_dao.get_tenant_attachment(db, attachment_id, tenant_id)
    if record is None:
        raise HTTPException(status_code=404, detail="附件不存在")
    await attachment_dao.restore(db, record)
    await db.commit()
    await db.refresh(record)
    return record


def disk_path(record: Attachment) -> Path:
    path = (settings.upload_path / (record.storage_key or "")).resolve()
    if not record.storage_key or settings.upload_path not in path.parents:
        raise HTTPException(status_code=404, detail="文件不存在")
    if not path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    return path


async def get_stats(db: AsyncSession, tenant_id: int | None) -> AttachmentStats:
    return AttachmentStats(**await attachment_dao.attachment_stats(db, tenant_id))
