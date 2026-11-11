import hashlib
import mimetypes
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.dao import attachment as attachment_dao
from app.models.attachment import Attachment
from app.schemas.attachment import AttachmentStats


def _category_for(mime_type: str, extension: str) -> str:
    if mime_type.startswith("image/"):
        return "image"
    if mime_type.startswith("video/"):
        return "video"
    if mime_type.startswith("audio/"):
        return "other"
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


async def list_attachments(
    db: AsyncSession,
    current: int,
    page_size: int,
    category: str | None = None,
    keyword: str | None = None,
    tenant_id: int = 1,
) -> tuple[list[Attachment], int]:
    return await attachment_dao.list_attachments(
        db, current, page_size, category, keyword, tenant_id
    )


async def save_upload(
    db: AsyncSession,
    file: UploadFile,
    source_module: str,
    tenant_id: int = 1,
    uploader: str = "admin",
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
                    raise HTTPException(status_code=413, detail="文件超过 50MB 限制")
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
            "source_module": source_module or "manual",
            "checksum": checksum.hexdigest(),
        },
    )
    await db.commit()
    await db.refresh(record)
    return record


async def delete_attachment(db: AsyncSession, attachment_id: int, tenant_id: int = 1) -> None:
    record = await attachment_dao.get_attachment(db, attachment_id, tenant_id)
    if record is None:
        raise HTTPException(status_code=404, detail="附件不存在")
    if record.storage_key:
        path = (settings.upload_path / record.storage_key).resolve()
        if settings.upload_path in path.parents:
            path.unlink(missing_ok=True)
    await attachment_dao.delete_attachment(db, record)
    await db.commit()


async def get_stats(db: AsyncSession, tenant_id: int = 1) -> AttachmentStats:
    return AttachmentStats(**await attachment_dao.attachment_stats(db, tenant_id))
