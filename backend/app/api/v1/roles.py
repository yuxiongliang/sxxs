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
    dependencies=[Depends(require_permission("role:read"))],
)
async def list_roles(
    current: int = Query(1, ge=1),
    pageSize: int = Query(100, ge=1, le=500),
    keyword: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    items, total = await role_service.list_roles(db, current, pageSize, keyword, status)
    return ok(page_data([RoleOut.model_validate(item) for item in items], total, current, pageSize))


@router.post(
    "",
    response_model=ApiResponse[RoleOut],
    dependencies=[Depends(require_permission("role:manage"))],
)
async def create_role(payload: RoleCreate, db: AsyncSession = Depends(get_db)):
    role = await role_service.create_role(db, payload)
    return ok(RoleOut.model_validate(role), "角色创建成功")


@router.put(
    "/{role_id}",
    response_model=ApiResponse[RoleOut],
    dependencies=[Depends(require_permission("role:manage"))],
)
async def update_role(role_id: int, payload: RoleUpdate, db: AsyncSession = Depends(get_db)):
    role = await role_service.update_role(db, role_id, payload)
    return ok(RoleOut.model_validate(role), "角色更新成功")


@router.delete(
    "/{role_id}",
    response_model=ApiResponse[None],
    dependencies=[Depends(require_permission("role:manage"))],
)
async def delete_role(role_id: int, db: AsyncSession = Depends(get_db)):
    await role_service.delete_role(db, role_id)
    return ok(None, "角色已删除")


@router.get(
    "/{role_id}/permissions",
    response_model=ApiResponse[dict],
    dependencies=[Depends(require_permission("role:read"))],
)
async def get_role_permissions(role_id: int, db: AsyncSession = Depends(get_db)):
    return ok(await role_service.get_role_permissions(db, role_id))


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
