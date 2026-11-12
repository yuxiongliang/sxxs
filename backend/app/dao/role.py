from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.role import Role
from app.models.user import User


async def list_roles(
    db: AsyncSession,
    current: int,
    page_size: int,
    keyword: str | None = None,
    status: str | None = None,
    exclude_codes: frozenset[str] | None = None,
) -> tuple[list[Role], int]:
    conditions = []
    if exclude_codes:
        conditions.append(Role.code.notin_(tuple(exclude_codes)))
    if keyword:
        pattern = f"%{keyword}%"
        conditions.append(or_(Role.name.ilike(pattern), Role.code.ilike(pattern)))
    if status:
        conditions.append(Role.status == status)

    count_stmt = select(func.count(Role.id))
    stmt = select(Role)
    if conditions:
        count_stmt = count_stmt.where(*conditions)
        stmt = stmt.where(*conditions)

    total = await db.scalar(count_stmt) or 0
    stmt = (
        stmt.order_by(Role.sort.asc(), Role.id.asc())
        .offset((current - 1) * page_size)
        .limit(page_size)
    )
    items = list((await db.scalars(stmt)).all())
    return items, total


async def get_role(db: AsyncSession, role_id: int) -> Role | None:
    return await db.get(Role, role_id)


async def get_by_code(db: AsyncSession, code: str) -> Role | None:
    result = await db.scalars(select(Role).where(Role.code == code))
    return result.first()


async def create_role(db: AsyncSession, data: dict) -> Role:
    role = Role(**data)
    db.add(role)
    await db.flush()
    await db.refresh(role)
    return role


async def delete_role(db: AsyncSession, role: Role) -> None:
    await db.delete(role)


async def count_users(db: AsyncSession, role_code: str) -> int:
    return await db.scalar(select(func.count(User.id)).where(User.role == role_code)) or 0
