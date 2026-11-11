from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Seller(Base, TimestampMixin):
    __tablename__ = "sellers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    display_name: Mapped[str] = mapped_column(String(128))
    seller_type: Mapped[str] = mapped_column(String(16), default="individual")
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    kyc_status: Mapped[str] = mapped_column(String(16), default="none")
    contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)


class Shop(Base, TimestampMixin):
    __tablename__ = "shops"
    __table_args__ = (UniqueConstraint("tenant_id", "slug", name="uq_shop_slug"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    slug: Mapped[str] = mapped_column(String(64))
    logo: Mapped[str | None] = mapped_column(String(512), nullable=True)
    banner: Mapped[str | None] = mapped_column(String(512), nullable=True)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    rating: Mapped[int] = mapped_column(Integer, default=0)
    sales_count: Mapped[int] = mapped_column(Integer, default=0)


class SellerMember(Base, TimestampMixin):
    __tablename__ = "seller_members"
    __table_args__ = (
        UniqueConstraint("tenant_id", "seller_id", "user_id", name="uq_seller_member"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(16), default="owner")
    status: Mapped[str] = mapped_column(String(16), default="active")
