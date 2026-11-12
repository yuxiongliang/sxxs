"""通知模板渲染。

核心规则：**变量缺失必须拦住**。把 `{{tenant_name}}` 原样发给买家是事故，
不是小瑕疵 —— 所以渲染失败抛 400 并列出缺失变量，而不是静默留空。

作用域（scope）三档，别混用：

* `platform`      —— 平台发给租户，品牌是平台；
* `tenant_buyer`  —— 租户发给买家（订单支付成功、发货提醒）；
* `tenant_seller` —— 租户发给卖家（新订单待处理、结算到账）。

历史数据里还有 `tenant`（买家/卖家未拆分）。它被当作 `tenant_buyer` 的别名：
写入时统一落成 `tenant_buyer`，读取买家作用域时会把老数据一起带出来。
"""

import re

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification_template import NotificationTemplate

VARIABLE_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")

# 只允许这些变量：白名单能防住「模板里塞表达式」这类注入
ALLOWED_VARIABLES = {
    "tenant_name",
    "tenant_domain",
    "buyer_name",
    "order_no",
    "amount",
    "site_url",
    "support_email",
}

# 变量中文释义与示例。**新增变量必须同时登记到这里**：平台端把这份清单
# 直接渲染成「可用变量」说明，漏登记等于运营看不到新变量。
VARIABLE_CATALOG: dict[str, dict[str, str]] = {
    "tenant_name": {
        "label": "站点名称",
        "description": "租户站点的名称：取租户的显示名（控制台「品牌 → 全站名称」），没设时用租户名。",
        "example": "示例二手市场",
    },
    "tenant_domain": {
        "label": "站点域名",
        "description": "该租户已生效的自定义域名；未绑定域名时为空，用了它要确保有值。",
        "example": "shop.example.com",
    },
    "buyer_name": {
        "label": "收件人",
        "description": "收信人称呼：发给买家是买家昵称，发给卖家是店主/店员名。",
        "example": "张三",
    },
    "order_no": {
        "label": "订单号",
        "description": "租户内唯一的订单编号，买家咨询时用它定位订单。",
        "example": "SO-20261112-0001",
    },
    "amount": {
        "label": "金额",
        "description": "已格式化的金额字符串（含货币符号），不要再自己拼「元」。",
        "example": "¥199.00",
    },
    "site_url": {
        "label": "站点地址",
        "description": "买家/卖家访问该租户站点的完整地址，用于「点这里查看」类文案。",
        "example": "https://shop.example.com",
    },
    "support_email": {
        "label": "客服邮箱",
        "description": "租户对外公布的客服邮箱，用于退订说明或「有问题请联系」。",
        "example": "support@example.com",
    },
}

PLATFORM_SCOPE = "platform"
BUYER_SCOPE = "tenant_buyer"
SELLER_SCOPE = "tenant_seller"
# 历史别名：买家/卖家尚未拆分时统一用的 tenant
LEGACY_TENANT_SCOPE = "tenant"
SCOPES = {PLATFORM_SCOPE, BUYER_SCOPE, SELLER_SCOPE}
TENANT_SCOPES = (BUYER_SCOPE, SELLER_SCOPE, LEGACY_TENANT_SCOPE)


def normalize_scope(scope: str) -> str:
    """把历史别名 tenant 归一到 tenant_buyer；未知值 400。"""
    value = (scope or "").strip()
    if value == LEGACY_TENANT_SCOPE:
        return BUYER_SCOPE
    if value not in SCOPES:
        raise HTTPException(
            status_code=400,
            detail="scope 只能是 platform / tenant_buyer / tenant_seller",
        )
    return value


def scope_values_for(scope: str) -> tuple[str, ...]:
    """库里应该匹配的值：买家作用域要把老的 tenant 行一起带出来。"""
    normalized = normalize_scope(scope)
    if normalized == BUYER_SCOPE:
        return (BUYER_SCOPE, LEGACY_TENANT_SCOPE)
    return (normalized,)


def variable_catalog() -> list[dict[str, str]]:
    """可用变量清单（平台端据此渲染中文注解）。顺序即展示顺序。"""
    order = (
        "tenant_name",
        "tenant_domain",
        "buyer_name",
        "order_no",
        "amount",
        "site_url",
        "support_email",
    )
    return [{"name": name, **VARIABLE_CATALOG[name]} for name in order if name in VARIABLE_CATALOG]


def extract_variables(*texts: str) -> list[str]:
    found: list[str] = []
    for text in texts:
        for match in VARIABLE_PATTERN.finditer(text or ""):
            name = match.group(1)
            if name not in found:
                found.append(name)
    return found


def validate_template_variables(*texts: str) -> list[str]:
    variables = extract_variables(*texts)
    unknown = [name for name in variables if name not in ALLOWED_VARIABLES]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"模板使用了不支持的变量：{'、'.join(unknown)}",
        )
    return variables


def render(text: str, context: dict[str, str]) -> str:
    """渲染并校验。缺失变量直接报错，不做静默替换。"""
    if not text:
        return ""
    missing = [name for name in extract_variables(text) if not str(context.get(name) or "").strip()]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"通知变量缺失：{'、'.join(missing)}",
        )

    def replace(match: re.Match[str]) -> str:
        return str(context[match.group(1)])

    return VARIABLE_PATTERN.sub(replace, text)


async def list_templates(
    db: AsyncSession,
    *,
    scope: str | None = None,
    scopes: tuple[str, ...] | None = None,
    only_enabled: bool = False,
) -> list[NotificationTemplate]:
    stmt = select(NotificationTemplate)
    if scope:
        stmt = stmt.where(NotificationTemplate.scope.in_(scope_values_for(scope)))
    elif scopes:
        stmt = stmt.where(NotificationTemplate.scope.in_(scopes))
    if only_enabled:
        stmt = stmt.where(NotificationTemplate.enabled.is_(True))
    stmt = stmt.order_by(NotificationTemplate.scope, NotificationTemplate.code)
    return list((await db.scalars(stmt)).all())


async def upsert_template(
    db: AsyncSession,
    *,
    scope: str,
    code: str,
    name: str,
    channel: str,
    subject: str,
    body: str,
    enabled: bool,
    mandatory: bool,
) -> NotificationTemplate:
    normalized = normalize_scope(scope)
    variables = validate_template_variables(subject, body)

    row = (
        await db.scalars(
            select(NotificationTemplate).where(
                NotificationTemplate.scope == normalized,
                NotificationTemplate.code == code,
            )
        )
    ).first()
    # 老的 tenant 行改存成 tenant_buyer：同一作用域内不能出现两条同 code
    if row is None:
        legacy = (
            await db.scalars(
                select(NotificationTemplate).where(
                    NotificationTemplate.scope == LEGACY_TENANT_SCOPE,
                    NotificationTemplate.code == code,
                )
            )
        ).first()
        if legacy is not None and normalized == BUYER_SCOPE:
            row = legacy
            row.scope = normalized
    if row is None:
        row = NotificationTemplate(scope=normalized, code=code)
        db.add(row)
    row.name = name
    row.channel = channel
    row.subject = subject
    row.body = body
    row.variables = variables
    row.enabled = enabled
    row.mandatory = mandatory
    row.version = (row.version or 0) + 1
    await db.commit()
    await db.refresh(row)
    return row
