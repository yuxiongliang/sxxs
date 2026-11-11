import secrets
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Product, ProductSku
from app.models.order import SellerOrder, Shipment
from app.models.seller import Seller, SellerMember, Shop
from app.schemas.commerce import SellerProductCreate
from app.services import audit as audit_service
from app.services import billing as billing_service
from app.services import finance as finance_service
from app.services.auth import AuthContext


async def current_seller(db: AsyncSession, context: AuthContext) -> tuple[Seller, Shop | None]:
    seller = (
        await db.scalars(
            select(Seller)
            .join(SellerMember, SellerMember.seller_id == Seller.id)
            .where(
                Seller.tenant_id == context.tenant.id,
                SellerMember.user_id == context.user.id,
                SellerMember.status == "active",
                Seller.status == "active",
            )
        )
    ).first()
    if seller is None:
        raise HTTPException(status_code=403, detail="当前账号不是卖家")
    shop = (
        await db.scalars(
            select(Shop).where(Shop.tenant_id == context.tenant.id, Shop.seller_id == seller.id)
        )
    ).first()
    return seller, shop


async def seller_products(db: AsyncSession, context: AuthContext) -> list[dict]:
    seller, _ = await current_seller(db, context)
    products = list(
        (
            await db.scalars(
                select(Product)
                .where(
                    Product.tenant_id == context.tenant.id,
                    Product.seller_id == seller.id,
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
        result.append(
            {
                "id": product.id,
                "name": product.name,
                "status": product.status,
                "price_cents": sku.price_cents if sku else 0,
                "stock": sku.stock if sku else 0,
            }
        )
    return result


async def create_seller_product(
    db: AsyncSession, context: AuthContext, payload: SellerProductCreate
) -> dict:
    seller, shop = await current_seller(db, context)
    if shop is None:
        raise HTTPException(status_code=400, detail="卖家店铺不存在")
    await billing_service.check_quota(db, context.tenant.id, "products")
    product = Product(
        tenant_id=context.tenant.id,
        seller_id=seller.id,
        shop_id=shop.id,
        category_id=payload.category_id,
        name=payload.name,
        subtitle=payload.subtitle,
        status="pending_review",
        created_by=context.user.id,
    )
    db.add(product)
    await db.flush()
    db.add(
        ProductSku(
            tenant_id=context.tenant.id,
            seller_id=seller.id,
            product_id=product.id,
            sku_code=f"SKU-{product.id}",
            name=payload.name,
            price_cents=payload.price_cents,
            stock=payload.stock,
            status="active",
        )
    )
    await db.commit()
    return {"id": product.id, "name": product.name, "status": product.status}


async def ship_seller_order(
    db: AsyncSession,
    context: AuthContext,
    seller_order_id: int,
    carrier: str,
    tracking_no: str,
) -> dict:
    seller, _ = await current_seller(db, context)
    seller_order = await db.get(SellerOrder, seller_order_id)
    if (
        seller_order is None
        or seller_order.tenant_id != context.tenant.id
        or seller_order.seller_id != seller.id
    ):
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
    await db.commit()
    return {"id": seller_order.id, "status": seller_order.status}


async def request_payout(db: AsyncSession, context: AuthContext):
    seller, _ = await current_seller(db, context)
    return await finance_service.create_payout(db, context, seller.id, requested_by=context.user.id)


async def seller_orders(db: AsyncSession, context: AuthContext) -> list[dict]:
    seller, _ = await current_seller(db, context)
    orders = list(
        (
            await db.scalars(
                select(SellerOrder)
                .where(
                    SellerOrder.tenant_id == context.tenant.id,
                    SellerOrder.seller_id == seller.id,
                )
                .order_by(SellerOrder.id.desc())
            )
        ).all()
    )
    return [
        {
            "id": item.id,
            "order_id": item.order_id,
            "seller_order_no": item.seller_order_no,
            "status": item.status,
            "goods_amount_cents": item.goods_amount_cents,
            "commission_amount_cents": item.commission_amount_cents,
            "payable_to_seller_cents": item.payable_to_seller_cents,
        }
        for item in orders
    ]


async def _find_membership(
    db: AsyncSession, context: AuthContext
) -> tuple[Seller, Shop | None] | None:
    """按成员关系找卖家（不看 status），用于区分「没申请」和「审核中」。"""
    seller = (
        await db.scalars(
            select(Seller)
            .join(SellerMember, SellerMember.seller_id == Seller.id)
            .where(
                Seller.tenant_id == context.tenant.id,
                SellerMember.user_id == context.user.id,
                SellerMember.status == "active",
            )
        )
    ).first()
    if seller is None:
        return None
    shop = (
        await db.scalars(
            select(Shop).where(Shop.tenant_id == context.tenant.id, Shop.seller_id == seller.id)
        )
    ).first()
    return seller, shop


async def seller_application(db: AsyncSession, context: AuthContext) -> dict:
    """当前用户的开店状态：未申请 / 审核中 / 已通过（被拒则回落为未申请）。"""
    found = await _find_membership(db, context)
    if found is None:
        return {"has_seller": False, "status": "none", "shop": None}
    seller, shop = found
    return {
        "has_seller": True,
        "status": seller.status,
        "seller_id": seller.id,
        "display_name": seller.display_name,
        "kyc_status": seller.kyc_status,
        "shop": (
            {"id": shop.id, "name": shop.name, "slug": shop.slug, "status": shop.status}
            if shop
            else None
        ),
    }


async def apply_seller(
    db: AsyncSession, context: AuthContext, shop_name: str, contact_phone: str = ""
) -> dict:
    """买家自助申请开店：建 pending 的卖家 + 店铺 + 店主成员关系。

    幂等语义：已经申请过（含审核中）返回 409，避免重复插入卖家/店铺。
    """
    found = await _find_membership(db, context)
    if found is not None:
        seller, _shop = found
        label = "审核中" if seller.status == "pending" else "已成为店主"
        raise HTTPException(status_code=409, detail=f"你{label}，无需重复申请")

    seller = Seller(
        tenant_id=context.tenant.id,
        owner_user_id=context.user.id,
        display_name=shop_name,
        seller_type="individual",
        status="pending",
        kyc_status="pending",
        contact_phone=contact_phone or None,
    )
    db.add(seller)
    await db.flush()

    shop = Shop(
        tenant_id=context.tenant.id,
        seller_id=seller.id,
        name=shop_name,
        slug=f"shop-{secrets.token_hex(4)}",
        status="active",
    )
    db.add(shop)
    db.add(
        SellerMember(
            tenant_id=context.tenant.id,
            seller_id=seller.id,
            user_id=context.user.id,
            role="owner",
            status="active",
        )
    )
    await audit_service.record(
        db,
        action=audit_service.ACTION_SELLER_APPLIED,
        tenant_id=context.tenant.id,
        actor_id=context.user.id,
        target_type="seller",
        target_id=seller.id,
        after={"display_name": shop_name, "status": "pending"},
    )
    await db.commit()
    await db.refresh(seller)
    await db.refresh(shop)
    return {
        "has_seller": True,
        "status": seller.status,
        "seller_id": seller.id,
        "display_name": seller.display_name,
        "kyc_status": seller.kyc_status,
        "shop": {"id": shop.id, "name": shop.name, "slug": shop.slug, "status": shop.status},
    }
