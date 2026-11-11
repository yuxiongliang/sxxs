import secrets

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.dao import department as department_dao
from app.dao import role as role_dao
from app.dao import user as user_dao
from app.models.permission import MemberRole
from app.models.tenant import TenantMember
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.services import billing as billing_service
from app.services.permission import bump_permission_version


async def list_users(
    db: AsyncSession,
    current: int,
    page_size: int,
    keyword: str | None = None,
    role: str | None = None,
    status: str | None = None,
    department_id: int | None = None,
    tenant_id: int = 1,
) -> tuple[list[User], int]:
    return await user_dao.list_users(
        db, current, page_size, keyword, role, status, department_id, tenant_id
    )


async def get_user_or_404(db: AsyncSession, user_id: int) -> User:
    user = await user_dao.get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


async def _validate_role(db: AsyncSession, role_code: str) -> None:
    role = await role_dao.get_by_code(db, role_code)
    if role is None:
        raise HTTPException(status_code=400, detail="角色不存在")
    if role.status != "active":
        raise HTTPException(status_code=400, detail="角色已停用")


async def _validate_department(
    db: AsyncSession, department_id: int | None, tenant_id: int = 1
) -> str | None:
    if department_id is None:
        return None
    department = await department_dao.get_department(db, department_id, tenant_id)
    if department is None:
        raise HTTPException(status_code=400, detail="部门不存在")
    if department.status != "active":
        raise HTTPException(status_code=400, detail="部门已停用")
    return department.name


async def create_user(db: AsyncSession, payload: UserCreate, tenant_id: int = 1) -> User:
    if await user_dao.get_by_username(db, payload.username):
        raise HTTPException(status_code=409, detail="用户名已存在")
    if await user_dao.get_by_email(db, payload.email):
        raise HTTPException(status_code=409, detail="邮箱已存在")
    if payload.status not in {"active", "disabled"}:
        raise HTTPException(status_code=400, detail="状态不合法")
    await _validate_role(db, payload.role)
    await billing_service.check_quota(db, tenant_id, "members")
    department_name = await _validate_department(db, payload.department_id, tenant_id)

    data = payload.model_dump(exclude={"password"})
    data["department"] = department_name
    data["password_hash"] = hash_password(payload.password)
    user = await user_dao.create_user(db, data)
    member = TenantMember(tenant_id=tenant_id, user_id=user.id, status=user.status)
    db.add(member)
    await db.flush()
    role = await role_dao.get_by_code(db, payload.role)
    if role is not None:
        db.add(MemberRole(member_id=member.id, role_id=role.id))
    await bump_permission_version(db, tenant_id)
    await db.commit()
    await db.refresh(user)
    return user


async def update_user(
    db: AsyncSession, user_id: int, payload: UserUpdate, tenant_id: int = 1
) -> User:
    user = await get_user_or_404(db, user_id)
    data = payload.model_dump(exclude_unset=True)
    if "email" in data and data["email"] != user.email:
        exists = await user_dao.get_by_email(db, data["email"])
        if exists and exists.id != user.id:
            raise HTTPException(status_code=409, detail="邮箱已存在")
    if "role" in data:
        await _validate_role(db, data["role"])
    if "department_id" in data:
        data["department"] = await _validate_department(db, data["department_id"], tenant_id)
    if "status" in data and data["status"] not in {"active", "disabled"}:
        raise HTTPException(status_code=400, detail="状态不合法")
    password = data.pop("password", None)
    if password:
        data["password_hash"] = hash_password(password)
    for key, value in data.items():
        setattr(user, key, value)
    if "role" in data:
        member = (
            await db.scalars(
                select(TenantMember).where(
                    TenantMember.tenant_id == tenant_id,
                    TenantMember.user_id == user.id,
                )
            )
        ).first()
        if member is not None:
            role = await role_dao.get_by_code(db, data["role"])
            if role is not None:
                await db.execute(delete(MemberRole).where(MemberRole.member_id == member.id))
                db.add(MemberRole(member_id=member.id, role_id=role.id))
        # A role change must invalidate the cached permission set immediately,
        # otherwise a demoted user keeps their old rights until the TTL expires.
        await bump_permission_version(db, tenant_id)
    await db.commit()
    await db.refresh(user)
    return user


async def delete_user(db: AsyncSession, user_id: int, tenant_id: int = 1) -> None:
    user = await get_user_or_404(db, user_id)
    if user.role == "admin" and await user_dao.count_admins(db) <= 1:
        raise HTTPException(status_code=400, detail="至少保留一个管理员账号")
    await db.execute(
        delete(MemberRole).where(
            MemberRole.member_id.in_(
                select(TenantMember.id).where(
                    TenantMember.tenant_id == tenant_id,
                    TenantMember.user_id == user.id,
                )
            )
        )
    )
    await db.execute(
        delete(TenantMember).where(
            TenantMember.tenant_id == tenant_id,
            TenantMember.user_id == user.id,
        )
    )
    await user_dao.delete_user(db, user)
    await bump_permission_version(db, tenant_id)
    await db.commit()


async def reset_password(db: AsyncSession, user_id: int) -> str:
    user = await get_user_or_404(db, user_id)
    temporary_password = f"Antd@{secrets.token_urlsafe(8)}"
    user.password_hash = hash_password(temporary_password)
    await db.commit()
    return temporary_password
