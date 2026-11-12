from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Attachment(Base):
    """附件。三个维度互相独立，任何一方都不能覆盖另一方：

    * `review_status` / `admin_hidden` —— **只有平台**能改（审核结论 / 强制下架）
    * `deleted_at`                       —— **只有租户**能改（软删，平台仍可取证）

    这三者塞进同一个 status 字段，必然出现「租户把驳回的图改回可用」或
    「平台取证时文件已被租户清空」两类事故。
    """

    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # NULL 表示平台自有资源（平台 logo / favicon），不属于任何租户
    tenant_id: Mapped[int | None] = mapped_column(
        ForeignKey("tenants.id"), index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(255))
    original_name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(128), default="application/octet-stream")
    size: Mapped[int] = mapped_column(BigInteger, default=0)
    extension: Mapped[str] = mapped_column(String(32), default="")
    category: Mapped[str] = mapped_column(String(16), default="other", index=True)
    storage: Mapped[str] = mapped_column(String(16), default="local")
    storage_key: Mapped[str] = mapped_column(String(255), default="")
    url: Mapped[str] = mapped_column(String(512), default="")
    uploader: Mapped[str] = mapped_column(String(64), default="admin")
    uploader_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    uploader_role: Mapped[str] = mapped_column(String(16), default="admin", index=True)
    source_module: Mapped[str] = mapped_column(String(64), default="manual", index=True)
    checksum: Mapped[str] = mapped_column(String(64), default="")

    # ---- 可见范围：public（logo 等公开资源）/ tenant / seller / buyer ----
    visibility: Mapped[str] = mapped_column(String(16), default="tenant", index=True)

    # ---- 审核（平台专属权力）----
    review_status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    review_kind: Mapped[str] = mapped_column(String(16), default="other")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # 给租户看的粗粒度原因（不可泄漏模型细节）
    reject_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # 强制下架：违规即时对所有人隐藏，独立于 review_status
    admin_hidden: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    thumbnail_key: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ---- 租户软删（平台仍可取证）----
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    deleted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
