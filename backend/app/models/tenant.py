from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
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


class TenantDomain(Base, TimestampMixin):
    """租户域名：Host → tenant 的唯一事实源（B6）。

    两类域名走不同的信任路径：

    * subdomain：{slug}.{tenant_base_domain}，域名归我们，创建即 active；
    * custom：客户自带域名，必须通过 DNS TXT 证明所有权后才 active —— 否则谁都
      能把别人的域名指到我们这儿，把一个「看起来是自家站」的假站点挂到买家面前。

    status 只有 active 参与 Host 解析；pending / failed / disabled 一律解析不出来。
    """

    __tablename__ = "tenant_domains"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    # 小写、不含端口与路径；唯一约束保证「一个 host 只能属于一个租户」
    host: Mapped[str] = mapped_column(String(253), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(16), default="custom")
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    verify_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class TenantMember(Base, TimestampMixin):
    __tablename__ = "tenant_members"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", name="uq_tenant_member"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
