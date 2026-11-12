from sqlalchemy import JSON, Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class PlatformSetting(Base, TimestampMixin):
    """平台级配置。

    与 `system_settings` 的区别：这里没有 tenant_id —— 配置属于整个 SaaS 平台，
    不随租户变化。租户级配置继续用 `system_settings`。

    `enabled` 语义很关键：**只有 enabled=True 时才代表平台真的接管了该类配置**。
    默认 false，这样存量租户切到 inherit 时会自动回落自己的历史配置，
    不会因为「平台还没填」而让全站支付/邮件立刻不可用。
    """

    __tablename__ = "platform_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    # 锁定后租户不可自定义（例如平台要求全站统一短信通道）
    policy_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    # 配置版本：改一次 +1，供缓存键与「是否变更」判断使用
    version: Mapped[int] = mapped_column(Integer, default=1)
