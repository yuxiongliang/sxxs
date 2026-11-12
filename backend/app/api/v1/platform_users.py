"""平台端用户总览：跨租户查看全站用户（只读）。

权限边界（用户明确要求）：

* 租户控制台 /users 只能看到「属于自己租户」的成员（按 TenantMember 过滤）；
* 平台端这个接口能看到全站所有用户 —— 因此它必须只对 aud=platform 的 token 开放。

只暴露展示必要字段，不返回密码哈希、refresh token 等任何凭据。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_platform_permission
from app.core.response import ok, page_data
from app.dao import user as user_dao
from app.models.user import User
from app.schemas.common import ApiResponse, PageData

router = APIRouter(prefix="/platform/users", tags=["平台用户"])


@router.put("/{user_id}/status", response_model=ApiResponse[dict])
async def set_user_status(
    user_id: int,
    payload: dict,
    context=Depends(require_platform_permission("platform:tenant:manage")),
    db: AsyncSession = Depends(get_db),
):
    """启用 / 停用某个用户（平台级）。

    两条硬约束：不能停用平台账号（root 等），也不能停用自己 —— 否则平台会把自己锁在门外。
    """
    status = str(payload.get("status") or "").strip()
    if status not in {"active", "disabled"}:
        raise HTTPException(status_code=400, detail="status 只能是 active 或 disabled")
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.is_platform_admin:
        raise HTTPException(status_code=400, detail="平台账号不能在这里停用")
    if user.id == context.user.id:
        raise HTTPException(status_code=400, detail="不能停用自己")
    user.status = status
    await db.commit()
    return ok({"id": user.id, "status": user.status}, "用户状态已更新")


@router.get("", response_model=ApiResponse[PageData[dict]])
async def list_platform_users(
    current: int = Query(1, ge=1),
    pageSize: int = Query(10, ge=1, le=100),
    keyword: str | None = None,
    status: str | None = None,
    _context=Depends(require_platform_permission("platform:tenant:read")),
    db: AsyncSession = Depends(get_db),
):
    """全站用户列表（跨租户）。keyword 同时匹配用户名/昵称/邮箱/手机号/用户ID。"""
    users, total = await user_dao.list_users(
        db, current, pageSize, keyword=keyword, status=status, tenant_id=None
    )
    return ok(
        page_data(
            [
                {
                    "id": user.id,
                    "public_id": user.public_id,
                    "username": user.username,
                    "nickname": user.nickname,
                    "email": user.email,
                    "phone": user.phone,
                    "role": user.role,
                    "status": user.status,
                    "is_platform_admin": user.is_platform_admin,
                    "created_at": user.created_at,
                }
                for user in users
            ],
            total,
            current,
            pageSize,
        )
    )
