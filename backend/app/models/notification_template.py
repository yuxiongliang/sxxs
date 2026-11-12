from sqlalchemy import JSON, Boolean, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class NotificationTemplate(Base, TimestampMixin):
    """通知模板。

    `scope` 区分三档，**不能混用**：
      * `platform`      —— 平台发给租户（订阅到期/欠费/平台公告），品牌是**平台**
      * `tenant_buyer`  —— 租户发给买家（订单/发货/退款），品牌是**租户**
      * `tenant_seller` —— 租户发给卖家（新订单/结算/审核），品牌是**租户**

    历史数据里的 `tenant` 视为 `tenant_buyer` 的别名，写入时归一成买家档。

    模板正文里用 `{{tenant_name}}` 这类变量，发送前必须渲染并校验，
    不允许把 `{{...}}` 原样发给用户。
    """

    __tablename__ = "notification_templates"
    __table_args__ = (
        UniqueConstraint("scope", "code", name="uq_notification_template_scope_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(16), default="tenant", index=True)
    code: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(128))
    channel: Mapped[str] = mapped_column(String(16), default="inbox")
    subject: Mapped[str] = mapped_column(String(200), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    variables: Mapped[list] = mapped_column(JSON, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # 合规/欠费等必须送达的通知，租户关不掉
    mandatory: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
