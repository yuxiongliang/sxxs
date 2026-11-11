from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dao import department as department_dao
from app.models.department import Department
from app.schemas.department import DepartmentCreate, DepartmentUpdate

VALID_STATUS = {"active", "disabled"}


async def list_departments(
    db: AsyncSession,
    current: int,
    page_size: int,
    keyword: str | None = None,
    status: str | None = None,
    tenant_id: int = 1,
) -> tuple[list[Department], int]:
    return await department_dao.list_departments(db, current, page_size, keyword, status, tenant_id)


async def get_department_or_404(
    db: AsyncSession, department_id: int, tenant_id: int = 1
) -> Department:
    department = await department_dao.get_department(db, department_id, tenant_id)
    if department is None:
        raise HTTPException(status_code=404, detail="部门不存在")
    return department


async def create_department(
    db: AsyncSession, payload: DepartmentCreate, tenant_id: int = 1
) -> Department:
    if await department_dao.get_by_name(db, payload.name, tenant_id):
        raise HTTPException(status_code=409, detail="部门名称已存在")
    if payload.status not in VALID_STATUS:
        raise HTTPException(status_code=400, detail="部门状态不合法")
    data = payload.model_dump()
    data["tenant_id"] = tenant_id
    department = await department_dao.create_department(db, data)
    await db.commit()
    await db.refresh(department)
    return department


async def update_department(
    db: AsyncSession, department_id: int, payload: DepartmentUpdate, tenant_id: int = 1
) -> Department:
    department = await get_department_or_404(db, department_id, tenant_id)
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] != department.name:
        exists = await department_dao.get_by_name(db, data["name"], tenant_id)
        if exists and exists.id != department.id:
            raise HTTPException(status_code=409, detail="部门名称已存在")
    if "status" in data and data["status"] not in VALID_STATUS:
        raise HTTPException(status_code=400, detail="部门状态不合法")
    for key, value in data.items():
        setattr(department, key, value)
    await db.commit()
    await db.refresh(department)
    return department


async def delete_department(db: AsyncSession, department_id: int, tenant_id: int = 1) -> None:
    department = await get_department_or_404(db, department_id, tenant_id)
    if await department_dao.count_users(db, department_id) > 0:
        raise HTTPException(status_code=409, detail="该部门仍被用户引用，不能删除")
    await department_dao.delete_department(db, department)
    await db.commit()
