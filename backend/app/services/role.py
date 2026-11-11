from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dao import role as role_dao
from app.models.permission import Permission, RolePermission
from app.models.role import Role
from app.schemas.role import RoleCreate, RoleUpdate
from app.services import audit as audit_service
from app.services.permission import bump_permission_version

VALID_STATUS = {"active", "disabled"}


async def list_roles(
    db: AsyncSession,
    current: int,
    page_size: int,
    keyword: str | None = None,
    status: str | None = None,
) -> tuple[list[Role], int]:
    return await role_dao.list_roles(db, current, page_size, keyword, status)


async def get_role_or_404(db: AsyncSession, role_id: int) -> Role:
    role = await role_dao.get_role(db, role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    return role


async def create_role(db: AsyncSession, payload: RoleCreate) -> Role:
    if await role_dao.get_by_code(db, payload.code):
        raise HTTPException(status_code=409, detail="角色编码已存在")
    if payload.status not in VALID_STATUS:
        raise HTTPException(status_code=400, detail="角色状态不合法")
    role = await role_dao.create_role(db, payload.model_dump())
    await db.commit()
    await db.refresh(role)
    return role


async def update_role(db: AsyncSession, role_id: int, payload: RoleUpdate) -> Role:
    role = await get_role_or_404(db, role_id)
    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"] not in VALID_STATUS:
        raise HTTPException(status_code=400, detail="角色状态不合法")
    for key, value in data.items():
        setattr(role, key, value)
    await db.commit()
    await db.refresh(role)
    return role


async def get_role_permissions(db: AsyncSession, role_id: int) -> dict:
    await get_role_or_404(db, role_id)
    all_permissions = list(
        (await db.scalars(select(Permission).order_by(Permission.module, Permission.code))).all()
    )
    selected = list(
        (
            await db.scalars(
                select(Permission.code)
                .join(RolePermission, RolePermission.permission_id == Permission.id)
                .where(RolePermission.role_id == role_id)
            )
        ).all()
    )
    return {
        "all": [
            {
                "code": item.code,
                "name": item.name,
                "module": item.module,
                "action": item.action,
            }
            for item in all_permissions
        ],
        "selected": selected,
    }


async def set_role_permissions(
    db: AsyncSession, role_id: int, tenant_id: int, permission_codes: list[str]
) -> dict:
    await get_role_or_404(db, role_id)
    permissions = list(
        (await db.scalars(select(Permission).where(Permission.code.in_(permission_codes)))).all()
    )
    if len(permissions) != len(set(permission_codes)):
        raise HTTPException(status_code=400, detail="包含不存在的权限码")
    existing = list(
        (await db.scalars(select(RolePermission).where(RolePermission.role_id == role_id))).all()
    )
    for item in existing:
        await db.delete(item)
    await db.flush()
    for permission in permissions:
        db.add(RolePermission(role_id=role_id, permission_id=permission.id))
    await bump_permission_version(db, tenant_id)
    await audit_service.record(
        db,
        action=audit_service.ACTION_ROLE_PERMISSIONS_UPDATED,
        tenant_id=tenant_id,
        target_type="role",
        target_id=role_id,
        after={"permission_codes": sorted(permission_codes)},
    )
    await db.commit()
    return await get_role_permissions(db, role_id)


async def delete_role(db: AsyncSession, role_id: int) -> None:
    role = await get_role_or_404(db, role_id)
    if await role_dao.count_users(db, role.code) > 0:
        raise HTTPException(status_code=409, detail="该角色仍被用户引用，不能删除")
    await role_dao.delete_role(db, role)
    await db.commit()
