import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.db import AsyncSessionLocal
from app.core.security import hash_password
from app.models.permission import MemberRole
from app.models.role import Role
from app.models.setting import SystemSetting
from app.models.tenant import Tenant, TenantMember
from app.models.user import User
from app.services import tenant_domains
from app.services.setting import DEFAULT_SETTINGS


async def create_tenant_cli(name: str, slug: str, email: str, nickname: str, password: str) -> None:
    async with AsyncSessionLocal() as db:
        tenant = (await db.scalars(select(Tenant).where(Tenant.slug == slug))).first()
        if tenant is None:
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

        member = (
            await db.scalars(
                select(TenantMember).where(
                    TenantMember.tenant_id == tenant.id,
                    TenantMember.user_id == user.id,
                )
            )
        ).first()
        if member is None:
            member = TenantMember(tenant_id=tenant.id, user_id=user.id, status="active")
            db.add(member)
            await db.flush()

        owner_role = (await db.scalars(select(Role).where(Role.code == "tenant_owner"))).first()
        if owner_role is None:
            raise RuntimeError("tenant_owner role is missing; start the API once first")
        existing_member_role = (
            await db.scalars(
                select(MemberRole).where(
                    MemberRole.member_id == member.id,
                    MemberRole.role_id == owner_role.id,
                )
            )
        ).first()
        if existing_member_role is None:
            db.add(MemberRole(member_id=member.id, role_id=owner_role.id))

        for category, default in DEFAULT_SETTINGS.items():
            setting = (
                await db.scalars(
                    select(SystemSetting).where(
                        SystemSetting.tenant_id == tenant.id,
                        SystemSetting.category == category,
                    )
                )
            ).first()
            if setting is None:
                db.add(
                    SystemSetting(
                        tenant_id=tenant.id,
                        category=category,
                        enabled=default["enabled"],
                        config=default["config"],
                    )
                )

        # 与 platform.create_tenant 保持一致：配了基域才建子域
        await tenant_domains.ensure_tenant_subdomain(db, tenant)

        await db.commit()
        print(f"tenant created: id={tenant.id} slug={tenant.slug}")
        print(f"owner login: {email} / {password}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a SaaS tenant and owner account")
    parser.add_argument("--name", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--nickname", default="租户管理员")
    parser.add_argument("--password", required=True)
    args = parser.parse_args()
    asyncio.run(create_tenant_cli(args.name, args.slug, args.email, args.nickname, args.password))


if __name__ == "__main__":
    main()
