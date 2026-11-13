from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_context, get_db, require_permission
from app.core.response import ok, page_data
from app.schemas.common import ApiResponse, PageData
from app.schemas.user import ResetPasswordResult, UserCreate, UserOut, UserUpdate
from app.services import user as user_service
from app.services.auth import AuthContext

router = APIRouter(prefix="/users", tags=["用户管理"])


@router.get(
    "",
    response_model=ApiResponse[PageData[UserOut]],
    dependencies=[Depends(require_permission("user:read"))],
)
async def list_users(
    current: int = Query(1, ge=1),
    pageSize: int = Query(10, ge=1, le=100),
    keyword: str | None = None,
    role: str | None = None,
    status: str | None = None,
    department_id: int | None = None,
    public_id: str | None = Query(default=None, max_length=32, description="用户编号，精确匹配"),
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    items, total = await user_service.list_users(
        db,
        current,
        pageSize,
        keyword,
        role,
        status,
        department_id,
        context.tenant.id,
        public_id,
    )
    return ok(page_data([UserOut.model_validate(item) for item in items], total, current, pageSize))


@router.post(
    "",
    response_model=ApiResponse[UserOut],
    dependencies=[Depends(require_permission("user:write"))],
)
async def create_user(
    payload: UserCreate,
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    user = await user_service.create_user(db, payload, context.tenant.id)
    return ok(UserOut.model_validate(user), "用户创建成功")


@router.put(
    "/{user_id}",
    response_model=ApiResponse[UserOut],
    dependencies=[Depends(require_permission("user:write"))],
)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    user = await user_service.update_user(db, user_id, payload, context.tenant.id)
    return ok(UserOut.model_validate(user), "用户更新成功")


@router.delete(
    "/{user_id}",
    response_model=ApiResponse[None],
    dependencies=[Depends(require_permission("user:write"))],
)
async def delete_user(
    user_id: int,
    context: AuthContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_db),
):
    await user_service.delete_user(db, user_id, context.tenant.id)
    return ok(None, "用户已删除")


@router.post(
    "/{user_id}/reset-password",
    response_model=ApiResponse[ResetPasswordResult],
    dependencies=[Depends(require_permission("user:write"))],
)
async def reset_password(
    user_id: int,
    context: AuthContext = Depends(require_permission("user:write")),
    db: AsyncSession = Depends(get_db),
):
    password = await user_service.reset_password(db, user_id, context.tenant.id)
    return ok(ResetPasswordResult(password=password), "密码已重置")
