from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class CartItem(Base, TimestampMixin):
    """A buyer's shopping-cart line.

    The cart is deliberately *not* a separate aggregate: one row per
    (tenant, buyer, sku) makes merge-on-add trivial and keeps price/stock reads
    bound to the live ``product_skus`` row at checkout time.
    """

    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint("tenant_id", "buyer_id", "sku_id", name="uq_cart_tenant_buyer_sku"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    sku_id: Mapped[int] = mapped_column(ForeignKey("product_skus.id"), index=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    selected: Mapped[bool] = mapped_column(Boolean, default=True)


class Address(Base, TimestampMixin):
    """Buyer shipping address book entry."""

    __tablename__ = "addresses"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", "receiver_name", "detail", name="uq_address_owner"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    receiver_name: Mapped[str] = mapped_column(String(64))
    receiver_phone: Mapped[str] = mapped_column(String(32))
    province: Mapped[str] = mapped_column(String(64), default="")
    city: Mapped[str] = mapped_column(String(64), default="")
    district: Mapped[str] = mapped_column(String(64), default="")
    detail: Mapped[str] = mapped_column(String(255))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


__all__ = ["Address", "CartItem"]
