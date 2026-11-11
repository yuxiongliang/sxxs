import secrets
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Product, ProductSku
from app.models.order import Order, OrderItem, Payment, Refund, SellerOrder, Shipment
from app.models.seller import Seller, Shop
from app.schemas.order import OrderCreateRequest
from app.services import audit as audit_service
from app.services import finance as finance_service
from app.services.auth import AuthContext


def _order_no(prefix: str) -> str:
    return f"{prefix}{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}{secrets.token_hex(3).upper()}"


async def create_order(
    db: AsyncSession, context: AuthContext, payload: OrderCreateRequest
) -> Order:
    sku_ids = [item.sku_id for item in payload.items]
    skus = list(
        (
            await db.scalars(
                select(ProductSku)
                .where(
                    ProductSku.tenant_id == context.tenant.id,
                    ProductSku.id.in_(sku_ids),
                    ProductSku.status == "active",
                )
                .with_for_update()
            )
        ).all()
    )
    sku_map = {item.id: item for item in skus}
    if len(sku_map) != len(set(sku_ids)):
        raise HTTPException(status_code=400, detail="部分 SKU 不存在或已下架")

    total = 0
    lines = []
    for item in payload.items:
        sku = sku_map[item.sku_id]
        if sku.stock < item.quantity:
            raise HTTPException(status_code=409, detail=f"SKU {sku.sku_code} 库存不足")
        product = await db.get(Product, sku.product_id)
        if product is None or product.status != "on_sale":
            raise HTTPException(status_code=400, detail="商品已下架")
        seller = await db.get(Seller, sku.seller_id)
        shop = await db.get(Shop, product.shop_id)
        if seller is None or shop is None or seller.status != "active":
            raise HTTPException(status_code=400, detail="卖家或店铺不可用")
        subtotal = sku.price_cents * item.quantity
        total += subtotal
        lines.append((sku, product, shop, seller, item.quantity, subtotal))

    order = Order(
        tenant_id=context.tenant.id,
        order_no=_order_no("ORD"),
        buyer_id=context.user.id,
        status="pending_payment",
        total_amount_cents=total,
        payable_amount_cents=total,
        receiver_name=payload.receiver_name,
        receiver_phone=payload.receiver_phone,
        receiver_address=payload.receiver_address,
        remark=payload.remark,
    )
    db.add(order)
    await db.flush()

    seller_orders: dict[int, SellerOrder] = {}
    for sku, product, shop, seller, quantity, subtotal in lines:
        seller_order = seller_orders.get(seller.id)
        if seller_order is None:
            seller_order = SellerOrder(
                tenant_id=context.tenant.id,
                order_id=order.id,
                seller_id=seller.id,
                shop_id=shop.id,
                seller_order_no=_order_no("SO"),
                status="pending_payment",
                goods_amount_cents=0,
                commission_amount_cents=0,
                payable_to_seller_cents=0,
            )
            db.add(seller_order)
            await db.flush()
            seller_orders[seller.id] = seller_order
        seller_order.goods_amount_cents += subtotal
        # Commission is configured per tenant / seller / category.
        rule = await finance_service.resolve_commission_rule(
            db, context.tenant.id, seller.id, product.category_id
        )
        commission = finance_service.compute_commission(subtotal, rule)
        seller_order.commission_amount_cents += commission
        seller_order.payable_to_seller_cents += subtotal - commission
        db.add(
            OrderItem(
                tenant_id=context.tenant.id,
                order_id=order.id,
                seller_order_id=seller_order.id,
                seller_id=seller.id,
                product_id=product.id,
                sku_id=sku.id,
                product_name=product.name,
                sku_name=sku.name,
                image=product.main_image,
                price_cents=sku.price_cents,
                quantity=quantity,
                subtotal_cents=subtotal,
            )
        )
        sku.stock -= quantity
        sku.locked_stock += quantity

    await audit_service.record(
        db,
        action=audit_service.ACTION_ORDER_CREATED,
        tenant_id=context.tenant.id,
        actor_id=context.user.id,
        target_type="order",
        target_id=order.id,
        after={
            "order_no": order.order_no,
            "payable_amount_cents": order.payable_amount_cents,
            "seller_order_count": len(seller_orders),
            "items": [{"sku_id": item.sku_id, "quantity": item.quantity} for item in payload.items],
        },
    )
    await db.commit()
    await db.refresh(order)
    return order


async def mock_pay(db: AsyncSession, context: AuthContext, order_id: int) -> Order:
    order = await db.get(Order, order_id)
    if order is None or order.tenant_id != context.tenant.id:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.status == "paid":
        return order
    if order.status != "pending_payment":
        raise HTTPException(status_code=400, detail="当前订单状态不可支付")
    order.status = "paid"
    order.paid_at = datetime.now(UTC)
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
    for seller_order in seller_orders:
        seller_order.status = "paid"
        await finance_service.record_order_ledger(db, seller_order)
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
    for item in items:
        sku = await db.get(ProductSku, item.sku_id)
        if sku is not None and sku.locked_stock >= item.quantity:
            sku.locked_stock -= item.quantity
    db.add(
        Payment(
            tenant_id=context.tenant.id,
            order_id=order.id,
            provider="mock",
            provider_trade_no=f"MOCK-{order.order_no}",
            amount_cents=order.payable_amount_cents,
            status="success",
            paid_at=order.paid_at,
        )
    )
    await audit_service.record(
        db,
        action=audit_service.ACTION_ORDER_PAID,
        tenant_id=context.tenant.id,
        actor_id=context.user.id,
        target_type="order",
        target_id=order.id,
        before={"status": "pending_payment"},
        after={
            "status": "paid",
            "order_no": order.order_no,
            "amount_cents": order.payable_amount_cents,
            "provider": "mock",
        },
    )
    await db.commit()
    await db.refresh(order)
    return order


async def cancel_order(db: AsyncSession, context: AuthContext, order_id: int) -> Order:
    order = await db.get(Order, order_id)
    if order is None or order.tenant_id != context.tenant.id:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.status != "pending_payment":
        raise HTTPException(status_code=400, detail="仅待支付订单可取消")
    previous_status = order.status
    order.status = "cancelled"
    order.cancelled_at = datetime.now(UTC)
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
    for seller_order in seller_orders:
        seller_order.status = "cancelled"
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
    for item in items:
        sku = await db.get(ProductSku, item.sku_id)
        if sku is not None:
            sku.stock += item.quantity
            sku.locked_stock = max(0, sku.locked_stock - item.quantity)
    await audit_service.record(
        db,
        action=audit_service.ACTION_ORDER_CANCELLED,
        tenant_id=context.tenant.id,
        actor_id=context.user.id,
        target_type="order",
        target_id=order.id,
        before={"status": previous_status},
        after={"status": order.status, "order_no": order.order_no},
    )
    await db.commit()
    await db.refresh(order)
    return order


async def ship_seller_order(
    db: AsyncSession,
    context: AuthContext,
    seller_order_id: int,
    carrier: str,
    tracking_no: str,
) -> SellerOrder:
    seller_order = await db.get(SellerOrder, seller_order_id)
    if seller_order is None or seller_order.tenant_id != context.tenant.id:
        raise HTTPException(status_code=404, detail="卖家订单不存在")
    if seller_order.status not in {"paid", "processing"}:
        raise HTTPException(status_code=400, detail="当前卖家订单不可发货")
    seller_order.status = "shipped"
    seller_order.shipped_at = datetime.now(UTC)
    db.add(
        Shipment(
            tenant_id=context.tenant.id,
            seller_order_id=seller_order.id,
            carrier=carrier,
            tracking_no=tracking_no,
            status="shipped",
        )
    )
    siblings = list(
        (
            await db.scalars(
                select(SellerOrder).where(
                    SellerOrder.tenant_id == context.tenant.id,
                    SellerOrder.order_id == seller_order.order_id,
                )
            )
        ).all()
    )
    all_shipped = all(item.status in {"shipped", "completed"} for item in siblings)
    order = await db.get(Order, seller_order.order_id)
    if order is not None:
        order.status = "shipped" if all_shipped else "partially_shipped"
    await audit_service.record(
        db,
        action=audit_service.ACTION_SELLER_ORDER_SHIPPED,
        tenant_id=context.tenant.id,
        actor_id=context.user.id,
        target_type="seller_order",
        target_id=seller_order.id,
        after={
            "status": seller_order.status,
            "carrier": carrier,
            "tracking_no": tracking_no,
            "order_id": seller_order.order_id,
        },
    )
    await db.commit()
    await db.refresh(seller_order)
    return seller_order


async def refund_seller_order(
    db: AsyncSession,
    context: AuthContext,
    seller_order_id: int,
    amount_cents: int,
    reason: str,
) -> Refund:
    seller_order = await db.get(SellerOrder, seller_order_id)
    if seller_order is None or seller_order.tenant_id != context.tenant.id:
        raise HTTPException(status_code=404, detail="卖家订单不存在")
    if seller_order.status == "refunded":
        raise HTTPException(status_code=400, detail="该卖家订单已退款")
    if amount_cents > seller_order.goods_amount_cents:
        raise HTTPException(status_code=400, detail="退款金额超过订单金额")
    refund = Refund(
        tenant_id=context.tenant.id,
        order_id=seller_order.order_id,
        seller_order_id=seller_order.id,
        amount_cents=amount_cents,
        reason=reason,
        status="refunded",
    )
    previous_status = seller_order.status
    previous_commission = seller_order.commission_amount_cents
    seller_order.status = "refunded"
    db.add(refund)
    await db.flush()
    # Give the goods money *and* the commission back, so the seller ledger nets
    # to zero instead of freezing refunded money forever.
    commission_reversed = await finance_service.record_refund_ledger(
        db, seller_order, refund.id, amount_cents
    )
    await audit_service.record(
        db,
        action=audit_service.ACTION_SELLER_ORDER_REFUNDED,
        tenant_id=context.tenant.id,
        actor_id=context.user.id,
        target_type="seller_order",
        target_id=seller_order.id,
        before={"status": previous_status},
        after={
            "status": "refunded",
            "amount_cents": amount_cents,
            "reason": reason,
            "commission_reversed_cents": commission_reversed,
            "commission_amount_cents": previous_commission,
        },
    )
    await db.commit()
    await db.refresh(refund)
    return refund


async def confirm_order(db: AsyncSession, context: AuthContext, order_id: int) -> Order:
    order = await db.get(Order, order_id)
    if order is None or order.tenant_id != context.tenant.id or order.buyer_id != context.user.id:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.status not in {"shipped", "partially_shipped"}:
        raise HTTPException(status_code=400, detail="当前订单不可确认收货")
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
    for seller_order in seller_orders:
        if seller_order.status == "shipped":
            seller_order.status = "completed"
            seller_order.completed_at = datetime.now(UTC)
    order.status = "completed"
    order.completed_at = datetime.now(UTC)
    await audit_service.record(
        db,
        action=audit_service.ACTION_ORDER_CONFIRMED,
        tenant_id=context.tenant.id,
        actor_id=context.user.id,
        target_type="order",
        target_id=order.id,
        after={"status": "completed", "order_no": order.order_no},
    )
    await db.commit()
    await db.refresh(order)
    return order
