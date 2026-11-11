"""Shopping cart and address book for the C-end portal.

Both aggregates are strictly scoped to ``context.tenant.id`` +
``context.user.id``: a buyer can never read or mutate another buyer's cart line
or address, and cross-tenant ids resolve to ``404`` rather than ``403`` so the
existence of foreign rows is not leaked.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cart import Address, CartItem
from app.models.catalog import Product, ProductSku
from app.models.seller import Seller, Shop
from app.schemas.cart import (
    AddressCreate,
    AddressUpdate,
    CartItemCreate,
    CartItemOut,
    CartItemUpdate,
    CartSummary,
    PortalProductDetail,
    ProductSkuOut,
)
from app.services.auth import AuthContext


async def product_detail(
    db: AsyncSession, context: AuthContext, product_id: int
) -> PortalProductDetail:
    product = await db.get(Product, product_id)
    if product is None or product.tenant_id != context.tenant.id:
        raise HTTPException(status_code=404, detail="商品不存在")
    if product.status != "on_sale":
        raise HTTPException(status_code=404, detail="商品已下架")

    seller = await db.get(Seller, product.seller_id)
    shop = await db.get(Shop, product.shop_id)
    skus = list(
        (
            await db.scalars(
                select(ProductSku)
                .where(
                    ProductSku.tenant_id == context.tenant.id,
                    ProductSku.product_id == product.id,
                    ProductSku.status == "active",
                )
                .order_by(ProductSku.id)
            )
        ).all()
    )
    return PortalProductDetail(
        id=product.id,
        name=product.name,
        subtitle=product.subtitle,
        description=product.description,
        status=product.status,
        main_image=product.main_image,
        images=product.images,
        seller_id=product.seller_id,
        seller_name=seller.display_name if seller else None,
        shop_id=product.shop_id,
        shop_name=shop.name if shop else None,
        skus=[ProductSkuOut.model_validate(sku) for sku in skus],
    )


async def _cart_rows(db: AsyncSession, context: AuthContext) -> list[CartItem]:
    return list(
        (
            await db.scalars(
                select(CartItem)
                .where(
                    CartItem.tenant_id == context.tenant.id,
                    CartItem.buyer_id == context.user.id,
                )
                .order_by(CartItem.id.desc())
            )
        ).all()
    )


async def _to_out(db: AsyncSession, item: CartItem) -> CartItemOut:
    product = await db.get(Product, item.product_id)
    sku = await db.get(ProductSku, item.sku_id)
    price = sku.price_cents if sku else 0
    stock = sku.stock if sku else 0
    available = bool(
        product is not None
        and product.status == "on_sale"
        and sku is not None
        and sku.status == "active"
        and stock >= item.quantity
    )
    return CartItemOut(
        id=item.id,
        product_id=item.product_id,
        sku_id=item.sku_id,
        seller_id=item.seller_id,
        quantity=item.quantity,
        selected=item.selected,
        product_name=product.name if product else "商品已删除",
        sku_name=sku.name if sku else "规格已删除",
        price_cents=price,
        stock=stock,
        main_image=product.main_image if product else None,
        subtotal_cents=price * item.quantity,
        available=available,
    )


async def get_cart(db: AsyncSession, context: AuthContext) -> CartSummary:
    items = [await _to_out(db, row) for row in await _cart_rows(db, context)]
    selected = [item for item in items if item.selected and item.available]
    return CartSummary(
        items=items,
        selected_count=sum(item.quantity for item in selected),
        selected_amount_cents=sum(item.subtotal_cents for item in selected),
        total_count=len(items),
        invalid_count=len([item for item in items if not item.available]),
    )


async def add_to_cart(
    db: AsyncSession, context: AuthContext, payload: CartItemCreate
) -> CartItemOut:
    sku = await db.get(ProductSku, payload.sku_id)
    if sku is None or sku.tenant_id != context.tenant.id or sku.status != "active":
        raise HTTPException(status_code=404, detail="SKU 不存在")
    product = await db.get(Product, sku.product_id)
    if product is None or product.status != "on_sale":
        raise HTTPException(status_code=400, detail="商品已下架")

    existing = (
        await db.scalars(
            select(CartItem).where(
                CartItem.tenant_id == context.tenant.id,
                CartItem.buyer_id == context.user.id,
                CartItem.sku_id == sku.id,
            )
        )
    ).first()

    if existing is not None:
        merged = existing.quantity + payload.quantity
        if merged > sku.stock:
            raise HTTPException(status_code=409, detail="库存不足")
        existing.quantity = merged
        existing.selected = True
        item = existing
    else:
        if payload.quantity > sku.stock:
            raise HTTPException(status_code=409, detail="库存不足")
        item = CartItem(
            tenant_id=context.tenant.id,
            buyer_id=context.user.id,
            product_id=product.id,
            sku_id=sku.id,
            seller_id=sku.seller_id,
            quantity=payload.quantity,
            selected=True,
        )
        db.add(item)

    await db.commit()
    await db.refresh(item)
    return await _to_out(db, item)


async def _own_item(db: AsyncSession, context: AuthContext, item_id: int) -> CartItem:
    item = await db.get(CartItem, item_id)
    if (
        item is None
        or item.tenant_id != context.tenant.id
        or item.buyer_id != context.user.id
    ):
        raise HTTPException(status_code=404, detail="购物车条目不存在")
    return item


async def update_cart_item(
    db: AsyncSession, context: AuthContext, item_id: int, payload: CartItemUpdate
) -> CartItemOut:
    item = await _own_item(db, context, item_id)
    if payload.quantity is not None:
        sku = await db.get(ProductSku, item.sku_id)
        if sku is None:
            raise HTTPException(status_code=400, detail="规格已删除")
        if payload.quantity > sku.stock:
            raise HTTPException(status_code=409, detail="库存不足")
        item.quantity = payload.quantity
    if payload.selected is not None:
        item.selected = payload.selected
    await db.commit()
    await db.refresh(item)
    return await _to_out(db, item)


async def remove_cart_item(db: AsyncSession, context: AuthContext, item_id: int) -> None:
    item = await _own_item(db, context, item_id)
    await db.delete(item)
    await db.commit()


async def clear_cart(db: AsyncSession, context: AuthContext) -> int:
    rows = await _cart_rows(db, context)
    for row in rows:
        await db.delete(row)
    await db.commit()
    return len(rows)


async def selected_cart_items(db: AsyncSession, context: AuthContext) -> list[CartItem]:
    items = await _cart_rows(db, context)
    return [item for item in items if item.selected]


async def drop_checked_out(db: AsyncSession, context: AuthContext, sku_ids: list[int]) -> None:
    if not sku_ids:
        return
    await db.execute(
        delete(CartItem).where(
            CartItem.tenant_id == context.tenant.id,
            CartItem.buyer_id == context.user.id,
            CartItem.sku_id.in_(sku_ids),
        )
    )
    await db.flush()


# --------------------------------------------------------------------------- #
# Address book
# --------------------------------------------------------------------------- #


async def _clear_default(db: AsyncSession, context: AuthContext, keep_id: int | None) -> None:
    rows = list(
        (
            await db.scalars(
                select(Address).where(
                    Address.tenant_id == context.tenant.id,
                    Address.user_id == context.user.id,
                    Address.is_default.is_(True),
                )
            )
        ).all()
    )
    for row in rows:
        if keep_id is not None and row.id == keep_id:
            continue
        row.is_default = False


async def list_addresses(db: AsyncSession, context: AuthContext) -> list[Address]:
    return list(
        (
            await db.scalars(
                select(Address)
                .where(
                    Address.tenant_id == context.tenant.id,
                    Address.user_id == context.user.id,
                )
                .order_by(Address.is_default.desc(), Address.id.desc())
            )
        ).all()
    )


async def create_address(
    db: AsyncSession, context: AuthContext, payload: AddressCreate
) -> Address:
    has_any = bool(await list_addresses(db, context))
    address = Address(
        tenant_id=context.tenant.id,
        user_id=context.user.id,
        receiver_name=payload.receiver_name,
        receiver_phone=payload.receiver_phone,
        province=payload.province,
        city=payload.city,
        district=payload.district,
        detail=payload.detail,
        # The first address becomes the default automatically.
        is_default=payload.is_default or not has_any,
    )
    db.add(address)
    await db.flush()
    if address.is_default:
        await _clear_default(db, context, address.id)
    await db.commit()
    await db.refresh(address)
    return address


async def _own_address(db: AsyncSession, context: AuthContext, address_id: int) -> Address:
    address = await db.get(Address, address_id)
    if (
        address is None
        or address.tenant_id != context.tenant.id
        or address.user_id != context.user.id
    ):
        raise HTTPException(status_code=404, detail="收货地址不存在")
    return address


async def update_address(
    db: AsyncSession, context: AuthContext, address_id: int, payload: AddressUpdate
) -> Address:
    address = await _own_address(db, context, address_id)
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(address, key, value)
    await db.flush()
    if data.get("is_default"):
        await _clear_default(db, context, address.id)
    await db.commit()
    await db.refresh(address)
    return address


async def set_default_address(
    db: AsyncSession, context: AuthContext, address_id: int
) -> Address:
    address = await _own_address(db, context, address_id)
    address.is_default = True
    await db.flush()
    await _clear_default(db, context, address.id)
    await db.commit()
    await db.refresh(address)
    return address


async def delete_address(db: AsyncSession, context: AuthContext, address_id: int) -> None:
    address = await _own_address(db, context, address_id)
    was_default = address.is_default
    await db.delete(address)
    await db.flush()
    if was_default:
        remaining = await list_addresses(db, context)
        if remaining:
            remaining[0].is_default = True
    await db.commit()


async def get_address(db: AsyncSession, context: AuthContext, address_id: int) -> Address:
    return await _own_address(db, context, address_id)
