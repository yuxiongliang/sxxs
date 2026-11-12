from sqlalchemy import JSON, Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class SystemSetting(Base, TimestampMixin):
    """租户级配置。

    `source` 决定这份配置是否生效：
      * `override`        —— 用租户自己的配置
      * `inherit`         —— 跟随平台（平台未启用时自动回落租户历史配置）
      * `forced_inherit`  —— 平台锁定，租户不可改（由平台写入，不由租户选择）
    """

    __tablename__ = "system_settings"
    __table_args__ = (UniqueConstraint("tenant_id", "category", name="uq_setting_tenant_category"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # 不再给 default=1：漏传 tenant_id 会直接报错，而不是静默读写 demo 租户
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    category: Mapped[str] = mapped_column(String(32), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(16), default="inherit", index=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
