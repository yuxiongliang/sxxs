from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    original_name: str
    mime_type: str
    size: int
    extension: str
    category: str
    storage: str
    url: str
    uploader: str
    uploader_role: str
    source_module: str
    checksum: str
    # 可见范围与审核状态：租户端只拿到粗粒度结论，看不到模型细节
    visibility: str
    review_status: str
    review_kind: str
    reject_reason: str | None = None
    admin_hidden: bool = False
    reviewed_at: datetime | None = None
    deleted_at: datetime | None = None
    created_at: datetime


class PlatformAttachmentOut(AttachmentOut):
    """平台审核视角：额外带租户信息与 provider（租户端绝不返回这两个字段）。"""

    tenant_id: int | None = None
    tenant_name: str | None = None
    review_provider: str | None = None


class AttachmentStats(BaseModel):
    total: int
    images: int
    videos: int
    documents: int
    others: int
    totalSize: int


class ModerationDecisionIn(BaseModel):
    decision: str
    categories: list[str] | None = None


class ModerationQueueStats(BaseModel):
    pending: int = 0
    manual: int = 0
    failed: int = 0
    rejected: int = 0
    approved: int = 0
    takedown: int = 0


class SignedUrlOut(BaseModel):
    url: str
    expires_in: int
