from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SettingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category: str
    enabled: bool
    config: dict[str, Any]
    updated_at: datetime


class SettingUpdate(BaseModel):
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)


class SettingTestRequest(BaseModel):
    config: dict[str, Any] | None = None


class SettingTestResult(BaseModel):
    success: bool
    message: str
    detail: dict[str, Any] | None = None
    qr_code: str | None = None
