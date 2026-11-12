from sqlalchemy import bindparam, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import TenantMember
from app.models.user import User


async def list_users(
    db: AsyncSession,
    current: int,
    page_size: int,
    keyword: str | None = None,
    role: str | None = None,
    status: str | None = None,
    department_id: int | None = None,
    tenant_id: int | None = None,
    public_id: str | None = None,
) -> tuple[list[User], int]:
    conditions = []
    if tenant_id is not None:
        conditions.append(
            User.id.in_(
                select(TenantMember.user_id).where(
                    TenantMember.tenant_id == tenant_id,
                    TenantMember.status == "active",
                )
            )
        )
    if keyword:
        like = bindparam("keyword_pattern", f"%{keyword}%")
        conditions.append(
            or_(
                User.username.ilike(like),
                User.nickname.ilike(like),
                User.email.ilike(like),
                User.phone.ilike(like),
                # 关键词里粘贴用户编号也能搜到
                User.public_id.ilike(like),
            )
        )
    if public_id:
        # 用户编号是精确值（唯一索引），不做模糊匹配
        conditions.append(User.public_id == public_id.strip())
    if role:
        conditions.append(User.role == role)
    if status:
        conditions.append(User.status == status)
    if department_id:
        conditions.append(User.department_id == department_id)

    count_stmt = select(func.count(User.id))
    stmt = select(User)
    if conditions:
        count_stmt = count_stmt.where(*conditions)
        stmt = stmt.where(*conditions)

    total = await db.scalar(count_stmt) or 0
    stmt = stmt.order_by(User.id.desc()).offset((current - 1) * page_size).limit(page_size)
    users = list((await db.scalars(stmt)).all())
    return users, total


async def get_user(db: AsyncSession, user_id: int) -> User | None:
    return await db.get(User, user_id)


async def get_by_username(db: AsyncSession, username: str) -> User | None:
    result = await db.scalars(select(User).where(User.username == username))
    return result.first()


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.scalars(select(User).where(User.email == email))
    return result.first()


async def count_admins(db: AsyncSession) -> int:
    return await db.scalar(select(func.count(User.id)).where(User.role == "admin")) or 0


async def create_user(db: AsyncSession, data: dict) -> User:
    user = User(**data)
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def delete_user(db: AsyncSession, user: User) -> None:
    await db.delete(user)
