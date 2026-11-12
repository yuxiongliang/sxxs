"""通知模板渲染。

核心规则：**变量缺失必须拦住**。把 `{{tenant_name}}` 原样发给买家是事故，
不是小瑕疵 —— 所以渲染失败抛 400 并列出缺失变量，而不是静默留空。
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
    "tenant_short_name",
    "tenant_domain",
    "buyer_name",
    "order_no",
    "amount",
    "site_url",
    "support_email",
}


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
    db: AsyncSession, *, scope: str | None = None, only_enabled: bool = False
) -> list[NotificationTemplate]:
    stmt = select(NotificationTemplate)
    if scope:
        stmt = stmt.where(NotificationTemplate.scope == scope)
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
    if scope not in {"platform", "tenant"}:
        raise HTTPException(status_code=400, detail="scope 只能是 platform 或 tenant")
    variables = validate_template_variables(subject, body)

    row = (
        await db.scalars(
            select(NotificationTemplate).where(
                NotificationTemplate.scope == scope,
                NotificationTemplate.code == code,
            )
        )
    ).first()
    if row is None:
        row = NotificationTemplate(scope=scope, code=code)
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
