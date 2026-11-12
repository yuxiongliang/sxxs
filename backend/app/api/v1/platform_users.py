"""平台端用户总览：跨租户查看全站用户（只读）。

权限边界（用户明确要求）：

* 租户控制台 /users 只能看到「属于自己租户」的成员（按 TenantMember 过滤）；
* 平台端这个接口能看到全站所有用户 —— 因此它必须只对 aud=platform 的 token 开放。

只暴露展示必要字段，不返回密码哈希、refresh token 等任何凭据。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_platform_permission
from app.core.response import ok, page_data
from app.dao import user as user_dao
from app.schemas.common import ApiResponse, PageData

router = APIRouter(prefix="/platform/users", tags=["平台用户"])


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
