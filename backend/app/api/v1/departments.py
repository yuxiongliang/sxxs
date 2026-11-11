from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_context, get_db, require_permission
from app.core.response import ok, page_data
from app.schemas.common import ApiResponse, PageData
from app.schemas.department import DepartmentCreate, DepartmentOut, DepartmentUpdate
from app.services import department as department_service
from app.services.auth import AuthContext

router = APIRouter(prefix="/departments", tags=["部门管理"])


@router.get(
    "",
    response_model=ApiResponse[PageData[DepartmentOut]],
    dependencies=[Depends(require_permission("department:read"))],
)
async def list_departments(
    current: int = Query(1, ge=1),
    pageSize: int = Query(100, ge=1, le=500),
    keyword: str | None = None,
    status: str | None = None,
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    items, total = await department_service.list_departments(
        db, current, pageSize, keyword, status, context.tenant.id
    )
    return ok(
        page_data(
            [DepartmentOut.model_validate(item) for item in items],
            total,
            current,
            pageSize,
        )
    )


@router.post(
    "",
    response_model=ApiResponse[DepartmentOut],
    dependencies=[Depends(require_permission("department:manage"))],
)
async def create_department(
    payload: DepartmentCreate,
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    department = await department_service.create_department(db, payload, context.tenant.id)
    return ok(DepartmentOut.model_validate(department), "部门创建成功")


@router.put(
    "/{department_id}",
    response_model=ApiResponse[DepartmentOut],
    dependencies=[Depends(require_permission("department:manage"))],
)
async def update_department(
    department_id: int,
    payload: DepartmentUpdate,
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    department = await department_service.update_department(
        db, department_id, payload, context.tenant.id
    )
    return ok(DepartmentOut.model_validate(department), "部门更新成功")


@router.delete(
    "/{department_id}",
    response_model=ApiResponse[None],
    dependencies=[Depends(require_permission("department:manage"))],
)
async def delete_department(
    department_id: int,
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    await department_service.delete_department(db, department_id, context.tenant.id)
    return ok(None, "部门已删除")
