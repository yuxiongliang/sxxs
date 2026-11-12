from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.permission import MemberRole
from app.models.role import Role
from app.models.setting import SystemSetting
from app.models.tenant import Tenant, TenantMember
from app.models.user import User
from app.services import service_category as category_service
from app.services import tenant_domains
from app.services.setting import DEFAULT_SETTINGS


async def list_tenants(db: AsyncSession) -> list[Tenant]:
    return list((await db.scalars(select(Tenant).order_by(Tenant.id))).all())


async def create_tenant(
    db: AsyncSession,
    name: str,
    slug: str,
    email: str | None = None,
    nickname: str | None = None,
    password: str | None = None,
    *,
    owner_user_id: int | None = None,
    service_category_id: int | None = None,
) -> Tenant:
    if (await db.scalars(select(Tenant).where(Tenant.slug == slug))).first():
        raise HTTPException(status_code=409, detail="租户 slug 已存在")
    tenant = Tenant(name=name, slug=slug, status="active")
    db.add(tenant)
    await db.flush()

    # 开通时就归类；不传表示暂未分类（不抽佣），运营可后补
    if service_category_id is not None:
        await category_service.assign_tenant(db, tenant, service_category_id)

    if owner_user_id is not None:
        # 平台端从用户列表里选人：直接把这个已有用户挂成租户管理员，不新建账号
        user = await db.get(User, owner_user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="用户不存在")
        if user.status != "active":
            raise HTTPException(status_code=400, detail="该用户已停用，不能作为租户管理员")
    else:
        if not email or not nickname or not password:
            raise HTTPException(status_code=400, detail="缺少管理员邮箱/昵称/初始密码")
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

    # 配了基域才建 <slug>.<基域>：基域为空时是 no-op，不替租户猜一个域名
    await tenant_domains.ensure_tenant_subdomain(db, tenant)

    await db.commit()
    await db.refresh(tenant)
    return tenant
