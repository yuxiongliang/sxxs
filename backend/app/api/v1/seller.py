from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_context, get_db, require_permission
from app.core.response import ok
from app.schemas.commerce import SellerApplyRequest, SellerProductCreate, SellerShipRequest
from app.services import seller_center as seller_service
from app.services.auth import AuthContext

router = APIRouter(prefix="/portal/seller", tags=["卖家中心"])


@router.get("/application")
async def seller_application(
    # 只返回调用者自己的开店状态，不涉及他人数据，因此不要求 seller:apply。
    # 若在这里要求该权限，已经是店主但角色不带 seller:apply 的账号
    # （如 operator + seller_owner）会被误判成「未开店」，看到「申请开店」。
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    """当前用户的开店状态：未申请 / 审核中 / 已通过。买家页面据此决定是否显示「我的店铺」。"""
    return ok(await seller_service.seller_application(db, context))


@router.post("/apply")
async def apply_seller(
    payload: SellerApplyRequest,
    context: AuthContext = Depends(require_permission("seller:apply")),
    db: AsyncSession = Depends(get_db),
):
    """买家自助申请开店：创建待审核的卖家与店铺，管理员在后台审核通过后即可经营。"""
    result = await seller_service.apply_seller(
        db, context, payload.shop_name, payload.contact_phone
    )
    return ok(result, "申请已提交，等待平台审核")


@router.get("/profile")
async def seller_profile(
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    seller, shop = await seller_service.current_seller(db, context)
    return ok(
        {
            "id": seller.id,
            "display_name": seller.display_name,
            "status": seller.status,
            "kyc_status": seller.kyc_status,
            "shop": {"id": shop.id, "name": shop.name, "slug": shop.slug} if shop else None,
        }
    )


@router.post("/products")
async def create_product(
    payload: SellerProductCreate,
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    return ok(await seller_service.create_seller_product(db, context, payload), "商品已提交审核")


@router.post("/orders/{seller_order_id}/ship")
async def ship_order(
    seller_order_id: int,
    payload: SellerShipRequest,
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    return ok(
        await seller_service.ship_seller_order(
            db, context, seller_order_id, payload.carrier, payload.tracking_no
        ),
        "发货成功",
    )


@router.post("/payouts")
async def request_payout(
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    payout = await seller_service.request_payout(db, context)
    return ok(
        {"id": payout.id, "amount_cents": payout.amount_cents, "status": payout.status}, "结算成功"
    )


@router.get("/products")
async def seller_products(
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    return ok(await seller_service.seller_products(db, context))


@router.get("/orders")
async def seller_orders(
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    return ok(await seller_service.seller_orders(db, context))
