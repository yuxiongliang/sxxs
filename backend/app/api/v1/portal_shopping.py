"""C-end portal shopping surface: product detail, cart, address book, checkout.

Every route is buyer-scoped (`context.tenant.id` + `context.user.id`). Order
creation is delegated to ``services.order.create_order`` so pricing, stock
locking and seller splitting stay in exactly one place.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_permission
from app.core.response import ok
from app.schemas.cart import (
    AddressCreate,
    AddressOut,
    AddressUpdate,
    CartItemCreate,
    CartItemUpdate,
    CartSummary,
    CheckoutFromCartRequest,
)
from app.schemas.order import OrderCreateRequest, OrderItemInput
from app.services import cart as cart_service
from app.services import order as order_service
from app.services.auth import AuthContext

router = APIRouter(prefix="/portal", tags=["买家商城"])


# --------------------------------------------------------------------------- #
# Product detail
# --------------------------------------------------------------------------- #


@router.get("/products/{product_id}")
async def portal_product_detail(
    product_id: int,
    context: AuthContext = Depends(require_permission("product:read")),
    db: AsyncSession = Depends(get_db),
):
    detail = await cart_service.product_detail(db, context, product_id)
    return ok(detail.model_dump())


# --------------------------------------------------------------------------- #
# Cart
# --------------------------------------------------------------------------- #


@router.get("/cart")
async def get_cart(
    context: AuthContext = Depends(require_permission("cart:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(CartSummary.model_validate(await cart_service.get_cart(db, context)).model_dump())


@router.post("/cart/items")
async def add_cart_item(
    payload: CartItemCreate,
    context: AuthContext = Depends(require_permission("cart:manage")),
    db: AsyncSession = Depends(get_db),
):
    item = await cart_service.add_to_cart(db, context, payload)
    return ok(item.model_dump(), "已加入购物车")


@router.put("/cart/items/{item_id}")
async def update_cart_item(
    item_id: int,
    payload: CartItemUpdate,
    context: AuthContext = Depends(require_permission("cart:manage")),
    db: AsyncSession = Depends(get_db),
):
    item = await cart_service.update_cart_item(db, context, item_id, payload)
    return ok(item.model_dump(), "购物车已更新")


@router.delete("/cart/items/{item_id}")
async def delete_cart_item(
    item_id: int,
    context: AuthContext = Depends(require_permission("cart:manage")),
    db: AsyncSession = Depends(get_db),
):
    await cart_service.remove_cart_item(db, context, item_id)
    return ok(None, "已移出购物车")


@router.delete("/cart")
async def clear_cart(
    context: AuthContext = Depends(require_permission("cart:manage")),
    db: AsyncSession = Depends(get_db),
):
    removed = await cart_service.clear_cart(db, context)
    return ok({"removed": removed}, "购物车已清空")


# --------------------------------------------------------------------------- #
# Address book
# --------------------------------------------------------------------------- #


@router.get("/addresses")
async def list_addresses(
    context: AuthContext = Depends(require_permission("address:read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await cart_service.list_addresses(db, context)
    return ok([AddressOut.model_validate(row).model_dump() for row in rows])


@router.post("/addresses")
async def create_address(
    payload: AddressCreate,
    context: AuthContext = Depends(require_permission("address:manage")),
    db: AsyncSession = Depends(get_db),
):
    address = await cart_service.create_address(db, context, payload)
    return ok(AddressOut.model_validate(address).model_dump(), "地址已保存")


@router.put("/addresses/{address_id}")
async def update_address(
    address_id: int,
    payload: AddressUpdate,
    context: AuthContext = Depends(require_permission("address:manage")),
    db: AsyncSession = Depends(get_db),
):
    address = await cart_service.update_address(db, context, address_id, payload)
    return ok(AddressOut.model_validate(address).model_dump(), "地址已更新")


@router.post("/addresses/{address_id}/default")
async def set_default_address(
    address_id: int,
    context: AuthContext = Depends(require_permission("address:manage")),
    db: AsyncSession = Depends(get_db),
):
    address = await cart_service.set_default_address(db, context, address_id)
    return ok(AddressOut.model_validate(address).model_dump(), "已设为默认地址")


@router.delete("/addresses/{address_id}")
async def delete_address(
    address_id: int,
    context: AuthContext = Depends(require_permission("address:manage")),
    db: AsyncSession = Depends(get_db),
):
    await cart_service.delete_address(db, context, address_id)
    return ok(None, "地址已删除")


# --------------------------------------------------------------------------- #
# Checkout from cart
# --------------------------------------------------------------------------- #


@router.post("/cart/checkout")
async def checkout_from_cart(
    payload: CheckoutFromCartRequest,
    context: AuthContext = Depends(require_permission("order:create")),
    db: AsyncSession = Depends(get_db),
):
    selected = await cart_service.selected_cart_items(db, context)
    if not selected:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="购物车中没有已选商品")

    receiver_address = dict(payload.receiver_address)
    if payload.address_id is not None:
        address = await cart_service.get_address(db, context, payload.address_id)
        receiver_address = {
            "province": address.province,
            "city": address.city,
            "district": address.district,
            "detail": address.detail,
        }

    order = await order_service.create_order(
        db,
        context,
        OrderCreateRequest(
            items=[
                OrderItemInput(sku_id=item.sku_id, quantity=item.quantity)
                for item in selected
            ],
            receiver_name=payload.receiver_name,
            receiver_phone=payload.receiver_phone,
            receiver_address=receiver_address,
            remark=payload.remark,
        ),
    )

    # Only the lines that actually became an order leave the cart.
    await cart_service.drop_checked_out(db, context, [item.sku_id for item in selected])
    await db.commit()

    return ok(
        {
            "id": order.id,
            "order_no": order.order_no,
            "status": order.status,
            "payable_amount_cents": order.payable_amount_cents,
        },
        "下单成功",
    )
