from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ModerationLog(Base):
    """每一次审核的完整证据链：谁、用哪个 provider、结论、耗时。

    申诉与排障都靠它 —— 没有这张表，「这张图为什么被驳回」永远说不清。
    """

    __tablename__ = "moderation_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    attachment_id: Mapped[int] = mapped_column(ForeignKey("attachments.id"), index=True)
    provider: Mapped[str] = mapped_column(String(32), default="null")
    decision: Mapped[str] = mapped_column(String(16), index=True)
    categories: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw: Mapped[dict] = mapped_column(JSON, default=dict)
    elapsed_ms: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(16), default="auto")
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ModerationCache(Base):
    """按文件内容去重审核结果：同一张图被多用户转发时只审一次。

    驳回结论永久缓存（不给「改个名字再传」留口子）。
    """

    __tablename__ = "moderation_cache"
    __table_args__ = (
        UniqueConstraint("checksum", "review_kind", name="uq_moderation_cache_checksum_kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    checksum: Mapped[str] = mapped_column(String(64), index=True)
    review_kind: Mapped[str] = mapped_column(String(16))
    decision: Mapped[str] = mapped_column(String(16))
    categories: Mapped[list] = mapped_column(JSON, default=list)
    provider: Mapped[str] = mapped_column(String(32), default="null")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
