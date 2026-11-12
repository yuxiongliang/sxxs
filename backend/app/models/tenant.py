from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    permission_version: Mapped[int] = mapped_column(Integer, default=1)
    # ---- 站点品牌（对外展示；通知模板的 {{tenant_name}} 也取这里）----
    # display_name 为空时回落到 name，避免存量租户没填就显示空白
    display_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    favicon_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    theme_color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # 账期：订单完成后资金需要冻结的天数，冻结期满才计入可结算余额。
    settlement_hold_days: Mapped[int] = mapped_column(Integer, default=7, server_default="7")


class TenantMember(Base, TimestampMixin):
    __tablename__ = "tenant_members"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", name="uq_tenant_member"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
