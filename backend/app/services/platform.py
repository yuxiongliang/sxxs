from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.permission import MemberRole
from app.models.role import Role
from app.models.setting import SystemSetting
from app.models.tenant import Tenant, TenantMember
from app.models.user import User
from app.services.setting import DEFAULT_SETTINGS


async def list_tenants(db: AsyncSession) -> list[Tenant]:
    return list((await db.scalars(select(Tenant).order_by(Tenant.id))).all())


async def create_tenant(
    db: AsyncSession, name: str, slug: str, email: str, nickname: str, password: str
) -> Tenant:
    if (await db.scalars(select(Tenant).where(Tenant.slug == slug))).first():
        raise HTTPException(status_code=409, detail="租户 slug 已存在")
    tenant = Tenant(name=name, slug=slug, status="active")
    db.add(tenant)
    await db.flush()

    user = (await db.scalars(select(User).where(User.email == email))).first()
    if user is None:
        user = User(
            username=email,
            nickname=nickname,
            email=email,
            role="tenant_owner",
            status="active",
            password_hash=hash_password(password),
        )
        db.add(user)
        await db.flush()
    else:
        user.password_hash = hash_password(password)
        user.status = "active"

    member = TenantMember(tenant_id=tenant.id, user_id=user.id, status="active")
    db.add(member)
    await db.flush()
    role = (await db.scalars(select(Role).where(Role.code == "tenant_owner"))).first()
    if role is not None:
        db.add(MemberRole(member_id=member.id, role_id=role.id))

    # Every new tenant starts on the default plan with its trial window.
    from app.services import billing as billing_service

    await billing_service.start_subscription(db, tenant.id, trial=True, commit=False)

    for category, default in DEFAULT_SETTINGS.items():
        db.add(
            SystemSetting(
                tenant_id=tenant.id,
                category=category,
                enabled=default["enabled"],
                config=default["config"],
            )
        )
    await db.commit()
    await db.refresh(tenant)
    return tenant
