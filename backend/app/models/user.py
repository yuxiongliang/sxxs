from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import new_public_id
from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # 对外的用户编号：随机 20 位、全局唯一（唯一性由索引兜底），不随主键变化
    public_id: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, default=lambda: new_public_id("usr")
    )
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    nickname: Mapped[str] = mapped_column(String(64))
    email: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    role: Mapped[str] = mapped_column(String(32), default="viewer", index=True)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    # Legacy department name kept for migration compatibility. New code uses department_id.
    department: Mapped[str | None] = mapped_column(String(64), nullable=True)
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id"), nullable=True, index=True
    )
    birthday: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(16), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 平台账号标识：与租户身份完全解耦。平台账号不需要任何 TenantMember 记录，
    # 登录后只拿 aud=platform 的 token，无法调用租户业务接口。
    is_platform_admin: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", index=True
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
