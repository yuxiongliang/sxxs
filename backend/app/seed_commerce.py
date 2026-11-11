from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Category, Product, ProductSku
from app.models.finance import CommissionRule
from app.models.order import Order, OrderItem, SellerOrder
from app.models.permission import MemberRole
from app.models.role import Role
from app.models.seller import Seller, SellerMember, Shop
from app.models.tenant import Tenant, TenantMember
from app.models.user import User


async def seed_commerce_data(db: AsyncSession) -> None:
    tenant = (await db.scalars(select(Tenant).where(Tenant.slug == "demo"))).first()
    if tenant is None:
        return

    owner = (await db.scalars(select(User).where(User.username == "lisi"))).first()
    buyer = (await db.scalars(select(User).where(User.username == "chenqi"))).first()
    if owner is None or buyer is None:
        return

    seller = (
        await db.scalars(
            select(Seller).where(Seller.tenant_id == tenant.id, Seller.owner_user_id == owner.id)
        )
    ).first()
    if seller is None:
        seller = Seller(
            tenant_id=tenant.id,
            owner_user_id=owner.id,
            display_name="李思的二手好物",
            seller_type="individual",
            status="active",
            kyc_status="approved",
        )
        db.add(seller)
        await db.flush()

    shop = (
        await db.scalars(
            select(Shop).where(Shop.tenant_id == tenant.id, Shop.seller_id == seller.id)
        )
    ).first()
    if shop is None:
        shop = Shop(
            tenant_id=tenant.id,
            seller_id=seller.id,
            name="李思的小店",
            slug="lisi-shop",
            description="C2C 演示店铺",
            status="active",
            rating=48,
            sales_count=12,
        )
        db.add(shop)
        await db.flush()

    member = (
        await db.scalars(
            select(TenantMember).where(
                TenantMember.tenant_id == tenant.id, TenantMember.user_id == owner.id
            )
        )
    ).first()
    if member is not None:
        seller_owner = (await db.scalars(select(Role).where(Role.code == "seller_owner"))).first()
        if seller_owner is not None:
            exists = (
                await db.scalars(
                    select(MemberRole).where(
                        MemberRole.member_id == member.id,
                        MemberRole.role_id == seller_owner.id,
                    )
                )
            ).first()
            if exists is None:
                db.add(MemberRole(member_id=member.id, role_id=seller_owner.id))

    seller_member = (
        await db.scalars(
            select(SellerMember).where(
                SellerMember.tenant_id == tenant.id,
                SellerMember.seller_id == seller.id,
                SellerMember.user_id == owner.id,
            )
        )
    ).first()
    if seller_member is None:
        db.add(
            SellerMember(
                tenant_id=tenant.id,
                seller_id=seller.id,
                user_id=owner.id,
                role="owner",
                status="active",
            )
        )

    category = (
        await db.scalars(
            select(Category).where(Category.tenant_id == tenant.id, Category.slug == "digital")
        )
    ).first()
    if category is None:
        category = Category(
            tenant_id=tenant.id, name="数码", slug="digital", sort=10, status="active"
        )
        db.add(category)
        await db.flush()

    product = (
        await db.scalars(
            select(Product).where(Product.tenant_id == tenant.id, Product.name == "九成新机械键盘")
        )
    ).first()
    if product is None:
        product = Product(
            tenant_id=tenant.id,
            seller_id=seller.id,
            shop_id=shop.id,
            category_id=category.id,
            name="九成新机械键盘",
            subtitle="自用闲置，功能正常",
            description="C2C 演示商品",
            status="on_sale",
            created_by=owner.id,
        )
        db.add(product)
        await db.flush()
        db.add(
            ProductSku(
                tenant_id=tenant.id,
                seller_id=seller.id,
                product_id=product.id,
                sku_code="KB-001",
                name="黑色 / 青轴",
                price_cents=19900,
                market_price_cents=39900,
                stock=10,
                status="active",
            )
        )
        await db.flush()

    sku = (
        await db.scalars(
            select(ProductSku).where(
                ProductSku.tenant_id == tenant.id, ProductSku.sku_code == "KB-001"
            )
        )
    ).first()
    order = (
        await db.scalars(
            select(Order).where(Order.tenant_id == tenant.id, Order.buyer_id == buyer.id)
        )
    ).first()
    if order is None and sku is not None:
        order = Order(
            tenant_id=tenant.id,
            order_no="DEMO-ORDER-001",
            buyer_id=buyer.id,
            status="paid",
            total_amount_cents=19900,
            payable_amount_cents=19900,
            receiver_name=buyer.nickname,
            receiver_phone=buyer.phone,
        )
        db.add(order)
        await db.flush()
        seller_order = SellerOrder(
            tenant_id=tenant.id,
            order_id=order.id,
            seller_id=seller.id,
            shop_id=shop.id,
            seller_order_no="DEMO-SO-001",
            status="paid",
            goods_amount_cents=19900,
            commission_amount_cents=1990,
            payable_to_seller_cents=17910,
        )
        db.add(seller_order)
        await db.flush()
        db.add(
            OrderItem(
                tenant_id=tenant.id,
                order_id=order.id,
                seller_order_id=seller_order.id,
                seller_id=seller.id,
                product_id=product.id,
                sku_id=sku.id,
                product_name=product.name,
                sku_name=sku.name,
                price_cents=sku.price_cents,
                quantity=1,
                subtotal_cents=sku.price_cents,
            )
        )

    await db.commit()

async def seed_commission_rule(db: AsyncSession) -> None:
    """Guarantee a tenant-wide default commission rule (10%)."""
    tenant = (await db.scalars(select(Tenant).where(Tenant.slug == "demo"))).first()
    if tenant is None:
        return
    existing = (
        await db.scalars(
            select(CommissionRule).where(
                CommissionRule.tenant_id == tenant.id,
                CommissionRule.seller_id.is_(None),
                CommissionRule.category_id.is_(None),
            )
        )
    ).first()
    if existing is not None:
        return
    db.add(
        CommissionRule(
            tenant_id=tenant.id,
            name="默认佣金规则",
            rate_bps=1000,
            fixed_fee_cents=0,
            priority=0,
            status="active",
        )
    )
    await db.commit()
