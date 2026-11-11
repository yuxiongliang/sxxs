from pydantic import BaseModel, Field


class OrderItemInput(BaseModel):
    sku_id: int
    quantity: int = Field(ge=1, le=999)


class OrderCreateRequest(BaseModel):
    items: list[OrderItemInput] = Field(min_length=1)
    receiver_name: str = Field(min_length=1, max_length=64)
    receiver_phone: str = Field(min_length=1, max_length=32)
    receiver_address: dict
    remark: str | None = None
