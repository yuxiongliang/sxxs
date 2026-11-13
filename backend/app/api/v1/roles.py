"""角色管理（租户控制台）。

`roles` 表既有系统共享角色（tenant_id 为空，所有租户只读可见），
也有租户自建角色（tenant_id 指向本租户）。平台角色（admin / platform_admin /
platform_support）不出现在租户侧，也改不了 —— 见 services/role.PLATFORM_ROLE_CODES。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_permission
from app.core.response import ok, page_data
from app.schemas.common import ApiResponse, PageData
from app.schemas.role import RoleCreate, RoleOut, RolePermissionsUpdate, RoleUpdate
from app.services import role as role_service
from app.services.auth import AuthContext

router = APIRouter(prefix="/roles", tags=["角色管理"])


@router.get(
    "",
    response_model=ApiResponse[PageData[RoleOut]],
)
async def list_roles(
    current: int = Query(1, ge=1),
    pageSize: int = Query(100, ge=1, le=500),
    keyword: str | None = None,
    status: str | None = None,
    context: AuthContext = Depends(require_permission("role:read")),
    db: AsyncSession = Depends(get_db),
):
    items, total = await role_service.list_roles(
        db, current, pageSize, keyword, status, context.tenant.id
    )
    return ok(page_data([RoleOut.model_validate(item) for item in items], total, current, pageSize))


@router.post(
    "",
    response_model=ApiResponse[RoleOut],
)
async def create_role(
    payload: RoleCreate,
    context: AuthContext = Depends(require_permission("role:manage")),
    db: AsyncSession = Depends(get_db),
):
    role = await role_service.create_role(db, payload, context.tenant.id)
    return ok(RoleOut.model_validate(role), "角色创建成功")


@router.put(
    "/{role_id}",
    response_model=ApiResponse[RoleOut],
)
async def update_role(
    role_id: int,
    payload: RoleUpdate,
    context: AuthContext = Depends(require_permission("role:manage")),
    db: AsyncSession = Depends(get_db),
):
    role = await role_service.update_role(db, role_id, payload, context.tenant.id)
    return ok(RoleOut.model_validate(role), "角色更新成功")


@router.delete(
    "/{role_id}",
    response_model=ApiResponse[None],
)
async def delete_role(
    role_id: int,
    context: AuthContext = Depends(require_permission("role:manage")),
    db: AsyncSession = Depends(get_db),
):
    await role_service.delete_role(db, role_id, context.tenant.id)
    return ok(None, "角色已删除")


@router.get(
    "/{role_id}/permissions",
    response_model=ApiResponse[dict],
)
async def get_role_permissions(
    role_id: int,
    context: AuthContext = Depends(require_permission("role:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await role_service.get_role_permissions(db, role_id, context.tenant.id))


@router.put(
    "/{role_id}/permissions",
    response_model=ApiResponse[dict],
)
async def set_role_permissions(
    role_id: int,
    payload: RolePermissionsUpdate,
    context: AuthContext = Depends(require_permission("role:manage")),
    db: AsyncSession = Depends(get_db),
):
    result = await role_service.set_role_permissions(
        db, role_id, context, payload.permission_codes
    )
    return ok(result, "角色权限已更新")
