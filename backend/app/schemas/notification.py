from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NotificationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    channel: str = "sms"
    template: str = ""
    audience: str = "all"
    content: str = ""
    scheduled_at: datetime | None = None


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    channel: str
    template: str
    audience: str
    content: str
    status: str
    scheduled_at: datetime | None = None
    sent_at: datetime | None = None
    total: int
    success_count: int
    failed_count: int
    error_message: str | None = None
    created_at: datetime


class NotificationStats(BaseModel):
    total: int
    success: int
    failed: int
    pending: int
    channels: dict[str, int]
