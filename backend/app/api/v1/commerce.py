from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_context, get_db, require_permission
from app.core.response import ok
from app.models.catalog import Product, ProductSku
from app.models.order import Order, OrderItem, SellerOrder
from app.models.seller import Seller
from app.schemas.commerce import (
    ProductReviewRequest,
    ProductUpdate,
    RefundCreateRequest,
    SellerReviewRequest,
    ShipmentCreateRequest,
)
from app.schemas.order import OrderCreateRequest
from app.services import finance as finance_service
from app.services import order as order_service
from app.services.auth import AuthContext

router = APIRouter(tags=["C2C 商城"])


def _seller_dict(seller: Seller) -> dict:
    return {
        "id": seller.id,
        "display_name": seller.display_name,
        "seller_type": seller.seller_type,
        "status": seller.status,
        "kyc_status": seller.kyc_status,
    }


def _product_dict(product: Product, sku: ProductSku | None = None) -> dict:
    data = {
        "id": product.id,
        "seller_id": product.seller_id,
        "shop_id": product.shop_id,
        "name": product.name,
        "subtitle": product.subtitle,
        "status": product.status,
        "main_image": product.main_image,
    }
    if sku is not None:
        data["sku"] = {
            "id": sku.id,
            "name": sku.name,
            "price_cents": sku.price_cents,
            "stock": sku.stock,
        }
    return data


@router.get("/admin/sellers")
async def admin_sellers(
    context: AuthContext = Depends(require_permission("seller:read")),
    db: AsyncSession = Depends(get_db),
):
    sellers = list(
        (
            await db.scalars(
                select(Seller).where(Seller.tenant_id == context.tenant.id).order_by(Seller.id)
            )
        ).all()
    )
    return ok([_seller_dict(item) for item in sellers])


@router.get("/admin/orders/{order_id}")
async def admin_order_detail(
    order_id: int,
    context: AuthContext = Depends(require_permission("order:read:tenant")),
    db: AsyncSession = Depends(get_db),
):
    order = await db.get(Order, order_id)
    if order is None or order.tenant_id != context.tenant.id:
        raise HTTPException(status_code=404, detail="订单不存在")
    seller_orders = list(
        (
            await db.scalars(
                select(SellerOrder).where(
                    SellerOrder.tenant_id == context.tenant.id,
                    SellerOrder.order_id == order.id,
                )
            )
        ).all()
    )
    items = list(
        (
            await db.scalars(
                select(OrderItem).where(
                    OrderItem.tenant_id == context.tenant.id,
                    OrderItem.order_id == order.id,
                )
            )
        ).all()
    )
    return ok(
        {
            "id": order.id,
            "order_no": order.order_no,
            "buyer_id": order.buyer_id,
            "status": order.status,
            "payable_amount_cents": order.payable_amount_cents,
            "seller_orders": [
                {
                    "id": item.id,
                    "seller_id": item.seller_id,
                    "status": item.status,
                    "goods_amount_cents": item.goods_amount_cents,
                    "commission_amount_cents": item.commission_amount_cents,
                    "payable_to_seller_cents": item.payable_to_seller_cents,
                }
                for item in seller_orders
            ],
            "items": [
                {
                    "id": item.id,
                    "product_name": item.product_name,
                    "sku_name": item.sku_name,
                    "price_cents": item.price_cents,
                    "quantity": item.quantity,
                    "subtotal_cents": item.subtotal_cents,
                }
                for item in items
            ],
        }
    )


@router.get("/admin/sellers/{seller_id}/ledger")
async def seller_ledger(
    seller_id: int,
    context: AuthContext = Depends(require_permission("payout:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await finance_service.seller_ledger(db, context, seller_id))


@router.post("/admin/sellers/{seller_id}/payouts")
async def create_payout(
    seller_id: int,
    context: AuthContext = Depends(require_permission("payout:manage")),
    db: AsyncSession = Depends(get_db),
):
    payout = await finance_service.create_payout(
        db, context, seller_id, requested_by=context.user.id
    )
    return ok(
        {"id": payout.id, "amount_cents": payout.amount_cents, "status": payout.status}, "结算完成"
    )


@router.post("/admin/sellers/{seller_id}/review")
async def review_seller(
    seller_id: int,
    payload: SellerReviewRequest,
    context: AuthContext = Depends(require_permission("seller:kyc")),
    db: AsyncSession = Depends(get_db),
):
    seller = await db.get(Seller, seller_id)
    if seller is None or seller.tenant_id != context.tenant.id:
        raise HTTPException(status_code=404, detail="卖家不存在")
    seller.status = payload.status
    seller.kyc_status = payload.kyc_status
    await db.commit()
    await db.refresh(seller)
    return ok(_seller_dict(seller), "卖家审核完成")


@router.get("/admin/products")
async def admin_products(
    context: AuthContext = Depends(require_permission("product:read")),
    db: AsyncSession = Depends(get_db),
):
    products = list(
        (
            await db.scalars(
                select(Product).where(Product.tenant_id == context.tenant.id).order_by(Product.id)
            )
        ).all()
    )
    return ok([_product_dict(item) for item in products])


@router.put("/admin/products/{product_id}")
async def update_product(
    product_id: int,
    payload: ProductUpdate,
    context: AuthContext = Depends(require_permission("product:manage")),
    db: AsyncSession = Depends(get_db),
):
    product = await db.get(Product, product_id)
    if product is None or product.tenant_id != context.tenant.id:
        raise HTTPException(status_code=404, detail="商品不存在")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, key, value)
    await db.commit()
    await db.refresh(product)
    return ok(_product_dict(product), "商品已更新")


@router.post("/admin/products/{product_id}/review")
async def review_product(
    product_id: int,
    payload: ProductReviewRequest,
    context: AuthContext = Depends(require_permission("product:moderate")),
    db: AsyncSession = Depends(get_db),
):
    product = await db.get(Product, product_id)
    if product is None or product.tenant_id != context.tenant.id:
        raise HTTPException(status_code=404, detail="商品不存在")
    product.status = payload.status
    await db.commit()
    await db.refresh(product)
    return ok(_product_dict(product), "商品审核完成")


@router.get("/admin/orders")
async def admin_orders(
    context: AuthContext = Depends(require_permission("order:read:tenant")),
    db: AsyncSession = Depends(get_db),
):
    orders = list(
        (
            await db.scalars(
                select(Order).where(Order.tenant_id == context.tenant.id).order_by(Order.id.desc())
            )
        ).all()
    )
    return ok(
        [
            {
                "id": item.id,
                "order_no": item.order_no,
                "buyer_id": item.buyer_id,
                "status": item.status,
                "payable_amount_cents": item.payable_amount_cents,
            }
            for item in orders
        ]
    )


@router.post("/admin/orders/{order_id}/mock-pay")
async def mock_pay_order(
    order_id: int,
    context: AuthContext = Depends(require_permission("order:manage")),
    db: AsyncSession = Depends(get_db),
):
    order = await order_service.mock_pay(db, context, order_id)
    return ok({"id": order.id, "order_no": order.order_no, "status": order.status}, "支付成功")


@router.post("/admin/orders/{order_id}/cancel")
async def cancel_order(
    order_id: int,
    context: AuthContext = Depends(require_permission("order:manage")),
    db: AsyncSession = Depends(get_db),
):
    order = await order_service.cancel_order(db, context, order_id)
    return ok({"id": order.id, "order_no": order.order_no, "status": order.status}, "订单已取消")


@router.post("/admin/seller-orders/{seller_order_id}/ship")
async def ship_order(
    seller_order_id: int,
    payload: ShipmentCreateRequest,
    context: AuthContext = Depends(require_permission("order:manage")),
    db: AsyncSession = Depends(get_db),
):
    seller_order = await order_service.ship_seller_order(
        db, context, seller_order_id, payload.carrier, payload.tracking_no
    )
    return ok({"id": seller_order.id, "status": seller_order.status}, "发货成功")


@router.post("/admin/seller-orders/{seller_order_id}/refund")
async def refund_order(
    seller_order_id: int,
    payload: RefundCreateRequest,
    context: AuthContext = Depends(require_permission("order:refund")),
    db: AsyncSession = Depends(get_db),
):
    refund = await order_service.refund_seller_order(
        db, context, seller_order_id, payload.amount_cents, payload.reason
    )
    return ok({"id": refund.id, "status": refund.status}, "退款成功")


@router.post("/portal/orders/{order_id}/confirm")
async def confirm_order(
    order_id: int,
    context: AuthContext = Depends(require_permission("order:read:self")),
    db: AsyncSession = Depends(get_db),
):
    order = await order_service.confirm_order(db, context, order_id)
    return ok({"id": order.id, "status": order.status}, "已确认收货")


@router.post("/portal/orders/{order_id}/mock-pay")
async def mock_pay_portal_order(
    order_id: int,
    context: AuthContext = Depends(require_permission("order:read:self")),
    db: AsyncSession = Depends(get_db),
):
    order = await db.get(Order, order_id)
    if order is None or order.tenant_id != context.tenant.id or order.buyer_id != context.user.id:
        raise HTTPException(status_code=404, detail="订单不存在")
    order = await order_service.mock_pay(db, context, order_id)
    return ok({"id": order.id, "status": order.status}, "支付成功")


@router.get("/portal/products")
async def portal_products(
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    products = list(
        (
            await db.scalars(
                select(Product)
                .where(
                    Product.tenant_id == context.tenant.id,
                    Product.status == "on_sale",
                )
                .order_by(Product.id.desc())
            )
        ).all()
    )
    result = []
    for product in products:
        sku = (
            await db.scalars(
                select(ProductSku).where(
                    ProductSku.tenant_id == context.tenant.id,
                    ProductSku.product_id == product.id,
                )
            )
        ).first()
        result.append(_product_dict(product, sku))
    return ok(result)


@router.post("/portal/orders")
async def create_portal_order(
    payload: OrderCreateRequest,
    context: AuthContext = Depends(require_permission("order:create")),
    db: AsyncSession = Depends(get_db),
):
    order = await order_service.create_order(db, context, payload)
    return ok(
        {
            "id": order.id,
            "order_no": order.order_no,
            "status": order.status,
            "payable_amount_cents": order.payable_amount_cents,
        },
        "订单创建成功",
    )


@router.get("/portal/orders")
async def portal_orders(
    context: AuthContext = Depends(require_permission("order:read:self")),
    db: AsyncSession = Depends(get_db),
):
    orders = list(
        (
            await db.scalars(
                select(Order)
                .where(
                    Order.tenant_id == context.tenant.id,
                    Order.buyer_id == context.user.id,
                )
                .order_by(Order.id.desc())
            )
        ).all()
    )
    return ok(
        [
            {
                "id": item.id,
                "order_no": item.order_no,
                "status": item.status,
                "payable_amount_cents": item.payable_amount_cents,
                "created_at": item.created_at,
            }
            for item in orders
        ]
    )


@router.get("/portal/orders/{order_id}")
async def portal_order_detail(
    order_id: int,
    context: AuthContext = Depends(require_permission("order:read:self")),
    db: AsyncSession = Depends(get_db),
):
    order = await db.get(Order, order_id)
    if order is None or order.tenant_id != context.tenant.id or order.buyer_id != context.user.id:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="订单不存在")
    seller_orders = list(
        (
            await db.scalars(
                select(SellerOrder).where(
                    SellerOrder.tenant_id == context.tenant.id,
                    SellerOrder.order_id == order.id,
                )
            )
        ).all()
    )
    items = list(
        (
            await db.scalars(
                select(OrderItem).where(
                    OrderItem.tenant_id == context.tenant.id,
                    OrderItem.order_id == order.id,
                )
            )
        ).all()
    )
    return ok(
        {
            "id": order.id,
            "order_no": order.order_no,
            "status": order.status,
            "payable_amount_cents": order.payable_amount_cents,
            "seller_orders": [
                {"id": item.id, "seller_id": item.seller_id, "status": item.status}
                for item in seller_orders
            ],
            "items": [
                {
                    "product_name": item.product_name,
                    "sku_name": item.sku_name,
                    "price_cents": item.price_cents,
                    "quantity": item.quantity,
                }
                for item in items
            ],
        }
    )
