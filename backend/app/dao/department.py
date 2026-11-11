from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.department import Department
from app.models.user import User


async def list_departments(
    db: AsyncSession,
    current: int,
    page_size: int,
    keyword: str | None = None,
    status: str | None = None,
    tenant_id: int = 1,
) -> tuple[list[Department], int]:
    conditions = [Department.tenant_id == tenant_id]
    if keyword:
        pattern = f"%{keyword}%"
        conditions.append(or_(Department.name.ilike(pattern), Department.code.ilike(pattern)))
    if status:
        conditions.append(Department.status == status)

    count_stmt = select(func.count(Department.id))
    stmt = select(Department)
    if conditions:
        count_stmt = count_stmt.where(*conditions)
        stmt = stmt.where(*conditions)

    total = await db.scalar(count_stmt) or 0
    stmt = (
        stmt.order_by(Department.sort.asc(), Department.id.asc())
        .offset((current - 1) * page_size)
        .limit(page_size)
    )
    items = list((await db.scalars(stmt)).all())
    return items, total


async def get_department(
    db: AsyncSession, department_id: int, tenant_id: int = 1
) -> Department | None:
    result = await db.scalars(
        select(Department).where(Department.id == department_id, Department.tenant_id == tenant_id)
    )
    return result.first()


async def get_by_name(db: AsyncSession, name: str, tenant_id: int = 1) -> Department | None:
    result = await db.scalars(
        select(Department).where(Department.name == name, Department.tenant_id == tenant_id)
    )
    return result.first()


async def create_department(db: AsyncSession, data: dict) -> Department:
    department = Department(**data)
    db.add(department)
    await db.flush()
    await db.refresh(department)
    return department


async def delete_department(db: AsyncSession, department: Department) -> None:
    await db.delete(department)


async def count_users(db: AsyncSession, department_id: int) -> int:
    return (
        await db.scalar(select(func.count(User.id)).where(User.department_id == department_id)) or 0
    )
