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


class SettingSourceUpdate(BaseModel):
    """租户保存设置。

    `config` 不传表示**只切换来源**，不改动租户已保存的配置 —— 否则前端
    在「跟随系统」时提交的是平台脱敏值（******），会把自己的配置毁掉。
    """

    source: str = Field(default="override", pattern="^(inherit|override)$")
    enabled: bool = True
    config: dict[str, Any] | None = None


class PlatformSettingUpdate(SettingUpdate):
    """平台保存设置：policy_locked 表示锁定后租户不可自定义。"""

    policy_locked: bool = False


class SettingResolvedOut(BaseModel):
    """租户视角的生效配置。

    **刻意不包含 platform_config**：那是平台的真实密钥，永远不下发给租户。
    """

    category: str
    source: str
    effective_source: str
    enabled: bool
    config: dict[str, Any]
    masked_fields: list[str] = Field(default_factory=list)
    platform_active: bool = False
    platform_updated_at: datetime | None = None
    policy_locked: bool = False
    inherit_allowed: bool = True
    tenant_config: dict[str, Any] | None = None


class SettingTestRequest(BaseModel):
    config: dict[str, Any] | None = None


class SettingTestResult(BaseModel):
    success: bool
    message: str
    detail: dict[str, Any] | None = None
    qr_code: str | None = None
