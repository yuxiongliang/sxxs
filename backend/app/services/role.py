from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dao import role as role_dao
from app.models.permission import Permission, RolePermission
from app.models.role import Role
from app.schemas.role import RoleCreate, RoleUpdate
from app.services import audit as audit_service
from app.services.auth import AuthContext
from app.services.permission import bump_permission_version

VALID_STATUS = {"active", "disabled"}

# 平台级角色：`roles` 是全库共享表，但这些角色只属于平台端。
# 租户控制台既不该看到它们，更不能改它们 —— `admin` 持有全部权限（含 platform:*），
# 一旦被租户改名/删权限，平台端会直接失去管理能力；而给租户角色塞进
# `platform:tenant:read` 就能读跨租户审计（见 services/audit.is_platform_viewer）。
PLATFORM_ROLE_CODES: frozenset[str] = frozenset(
    {"admin", "platform_admin", "platform_support"}
)


def is_platform_role(role: Role) -> bool:
    return role.code in PLATFORM_ROLE_CODES


async def list_roles(
    db: AsyncSession,
    current: int,
    page_size: int,
    keyword: str | None = None,
    status: str | None = None,
    tenant_id: int | None = None,
) -> tuple[list[Role], int]:
    """租户控制台的角色列表：平台角色一律不出现，别的租户的自建角色也不出现。"""
    return await role_dao.list_roles(
        db,
        current,
        page_size,
        keyword,
        status,
        exclude_codes=PLATFORM_ROLE_CODES,
        tenant_id=tenant_id,
    )


async def get_role_or_404(
    db: AsyncSession,
    role_id: int,
    *,
    allow_platform: bool = False,
    tenant_id: int | None = None,
    for_write: bool = False,
) -> Role:
    role = await role_dao.get_role(db, role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    # 平台角色对租户等于「不存在」：返回 403 而不是 404，方便前端提示，
    # 也不会泄露该 id 是否真实存在之外的信息。
    if not allow_platform and is_platform_role(role):
        raise HTTPException(status_code=403, detail="平台角色不可在租户控制台维护")
    if tenant_id is not None:
        # 别的租户自建的角色：对本租户等于不存在
        if role.tenant_id is not None and role.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="角色不存在")
        # 系统共享角色（tenant_id 为空）所有租户都在用，不能由某一个租户改
        if for_write and role.tenant_id is None:
            raise HTTPException(
                status_code=403,
                detail="系统内置角色为全租户共享、只读；如需调整请新建一个本租户角色",
            )
    return role


async def create_role(db: AsyncSession, payload: RoleCreate, tenant_id: int | None = None) -> Role:
    if await role_dao.get_by_code(db, payload.code):
        raise HTTPException(status_code=409, detail="角色编码已存在")
    if payload.status not in VALID_STATUS:
        raise HTTPException(status_code=400, detail="角色状态不合法")
    if payload.code in PLATFORM_ROLE_CODES:
        raise HTTPException(status_code=400, detail="平台角色编码已被占用")
    role = await role_dao.create_role(db, {**payload.model_dump(), "tenant_id": tenant_id})
    await db.commit()
    await db.refresh(role)
    return role


async def update_role(
    db: AsyncSession, role_id: int, payload: RoleUpdate, tenant_id: int | None = None
) -> Role:
    role = await get_role_or_404(db, role_id, tenant_id=tenant_id, for_write=True)
    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"] not in VALID_STATUS:
        raise HTTPException(status_code=400, detail="角色状态不合法")
    for key, value in data.items():
        setattr(role, key, value)
    await db.commit()
    await db.refresh(role)
    return role


async def get_role_permissions(
    db: AsyncSession, role_id: int, tenant_id: int | None = None
) -> dict:
    await get_role_or_404(db, role_id, tenant_id=tenant_id)
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


def _guard_permission_grants(context: AuthContext, permission_codes: list[str]) -> None:
    """防提权：只能授出自己已有的权限，且平台权限一律不得落到租户角色上。"""
    platform_codes = sorted(code for code in permission_codes if code.startswith("platform:"))
    if platform_codes:
        raise HTTPException(
            status_code=403,
            detail=f"平台权限不可授予租户角色：{', '.join(platform_codes)}",
        )
    escalated = sorted(set(permission_codes) - set(context.permissions))
    if escalated:
        raise HTTPException(
            status_code=403,
            detail=f"不能授予自己没有的权限：{', '.join(escalated)}",
        )


async def set_role_permissions(
    db: AsyncSession, role_id: int, context: AuthContext, permission_codes: list[str]
) -> dict:
    await get_role_or_404(
        db, role_id, tenant_id=context.tenant.id, for_write=True
    )
    tenant_id = context.tenant.id
    _guard_permission_grants(context, permission_codes)
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


async def delete_role(db: AsyncSession, role_id: int, tenant_id: int | None = None) -> None:
    role = await get_role_or_404(db, role_id, tenant_id=tenant_id, for_write=True)
    if await role_dao.count_users(db, role.code) > 0:
        raise HTTPException(status_code=409, detail="该角色仍被用户引用，不能删除")
    # 先清掉权限关联：role_permissions 有外键，不先删会让删除直接 500
    linked = list(
        (await db.scalars(select(RolePermission).where(RolePermission.role_id == role_id))).all()
    )
    for item in linked:
        await db.delete(item)
    await db.flush()
    await role_dao.delete_role(db, role)
    await db.commit()
