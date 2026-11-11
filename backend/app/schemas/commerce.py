from pydantic import BaseModel, Field


class SellerReviewRequest(BaseModel):
    status: str = Field(pattern="^(active|suspended|closed)$")
    kyc_status: str = Field(pattern="^(none|pending|approved|rejected)$")


class ProductReviewRequest(BaseModel):
    status: str = Field(pattern="^(draft|pending_review|on_sale|off_sale|rejected)$")


class ShipmentCreateRequest(BaseModel):
    carrier: str = Field(min_length=1, max_length=64)
    tracking_no: str = Field(min_length=1, max_length=128)


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    subtitle: str | None = Field(default=None, max_length=255)
    description: str | None = None
    status: str | None = None
    main_image: str | None = Field(default=None, max_length=512)
    images: list[str] | None = None


class SellerProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    subtitle: str | None = Field(default=None, max_length=255)
    price_cents: int = Field(gt=0)
    stock: int = Field(ge=0)
    category_id: int | None = None


class RefundCreateRequest(BaseModel):
    amount_cents: int = Field(gt=0)
    reason: str = Field(default="", max_length=255)


class SellerShipRequest(BaseModel):
    carrier: str = Field(min_length=1, max_length=64)
    tracking_no: str = Field(min_length=1, max_length=128)


class SellerApplyRequest(BaseModel):
    """买家申请开店。"""

    shop_name: str = Field(min_length=2, max_length=64)
    contact_phone: str = Field(default="", max_length=32)
