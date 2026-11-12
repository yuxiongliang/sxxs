"""平台通知模板管理。只接受 aud=platform 的 token。"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_platform_permission
from app.core.response import ok
from app.schemas.common import ApiResponse
from app.services import notification_template as template_service

router = APIRouter(prefix="/platform/notification-templates", tags=["平台通知模板"])

MANAGE = "platform:notification:manage"


class TemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    channel: str = Field(default="inbox", max_length=16)
    subject: str = ""
    body: str = ""
    enabled: bool = True
    mandatory: bool = False


def _serialize(row) -> dict:
    return {
        "id": row.id,
        "scope": row.scope,
        "code": row.code,
        "name": row.name,
        "channel": row.channel,
        "subject": row.subject,
        "body": row.body,
        "variables": row.variables,
        "enabled": row.enabled,
        "mandatory": row.mandatory,
        "version": row.version,
        "updated_at": row.updated_at,
    }


@router.get("", response_model=ApiResponse[list[dict]])
async def list_templates(
    scope: str | None = Query(default=None),
    _context=Depends(require_platform_permission("platform:setting:read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await template_service.list_templates(db, scope=scope)
    return ok([_serialize(row) for row in rows])


@router.get("/variables", response_model=ApiResponse[list[dict]])
async def list_variables(
    _context=Depends(require_platform_permission("platform:setting:read")),
):
    """可用变量清单 + 中文释义。前端据此渲染「可用变量」说明，新增变量自动出现。"""
    return ok(template_service.variable_catalog())


@router.put("/{scope}/{code}", response_model=ApiResponse[dict])
async def save_template(
    scope: str,
    code: str,
    payload: TemplateIn,
    _context=Depends(require_platform_permission(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    row = await template_service.upsert_template(
        db,
        scope=scope,
        code=code,
        name=payload.name,
        channel=payload.channel,
        subject=payload.subject,
        body=payload.body,
        enabled=payload.enabled,
        mandatory=payload.mandatory,
    )
    return ok(_serialize(row), "模板已保存")
