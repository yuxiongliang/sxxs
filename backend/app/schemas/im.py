from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MessageType = Literal["text", "image"]
ReportAction = Literal["accept", "reject"]


class ConversationCreate(BaseModel):
    seller_id: int
    order_id: int | None = None


class MessageCreate(BaseModel):
    """A chat message is either free text or an uploaded image.

    * ``type="text"``  -> ``content`` is required, whitespace-only is rejected.
    * ``type="image"`` -> ``attachment_id`` is required and ``content`` becomes an
      optional caption.
    """

    type: MessageType = "text"
    content: str = Field(default="", max_length=5000)
    attachment_id: int | None = None
    client_msg_id: str = Field(min_length=1, max_length=64)

    @field_validator("content")
    @classmethod
    def _strip_content(cls, value: str) -> str:
        return value.strip()

    @field_validator("client_msg_id")
    @classmethod
    def _reject_blank_client_msg_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("client_msg_id 不能为空")
        return stripped

    @model_validator(mode="after")
    def _validate_payload(self) -> "MessageCreate":
        if self.type == "text" and not self.content:
            raise ValueError("消息内容不能为空")
        if self.type == "image" and self.attachment_id is None:
            raise ValueError("图片消息必须提供 attachment_id")
        return self


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    buyer_id: int
    seller_id: int
    order_id: int | None = None
    status: str
    buyer_unread_count: int
    seller_unread_count: int


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    sender_id: int
    client_msg_id: str
    seq: int
    type: str
    content: str
    payload: dict | None = None
    status: str


class ReadReceiptRequest(BaseModel):
    seq: int = Field(ge=1)


class ReadStateOut(BaseModel):
    conversation_id: int
    my_last_read_seq: int
    peer_last_read_seq: int
    buyer_unread_count: int
    seller_unread_count: int


class ReportCreate(BaseModel):
    reason: str = Field(min_length=1, max_length=255)

    @field_validator("reason")
    @classmethod
    def _strip_reason(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("举报原因不能为空")
        return stripped


class ReportHandleRequest(BaseModel):
    action: ReportAction
    note: str = Field(default="", max_length=255)


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    message_id: int
    reporter_id: int
    reason: str
    status: str
    note: str
