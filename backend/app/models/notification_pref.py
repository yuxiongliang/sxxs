from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class TenantNotificationPref(Base, TimestampMixin):
    """租户的渠道开关。

    `inbox`（站内信）是**强制开启**的：欠费、安全、合规类通知必须送达，
    所以不允许出现在这张表的可关闭集合里 —— 只能关短信/邮件。
    """

    __tablename__ = "tenant_notification_prefs"
    __table_args__ = (UniqueConstraint("tenant_id", "channel", name="uq_tenant_notification_pref"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    channel: Mapped[str] = mapped_column(String(16))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
