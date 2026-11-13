from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    description: str | None = None
    status: str
    sort: int
    # NULL = 系统共享角色（所有租户只读可见）；非 NULL = 该租户自建角色
    tenant_id: int | None = None
    created_at: datetime
    updated_at: datetime


class RoleCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=255)
    status: str = "active"
    sort: int = 0


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=255)
    status: str | None = None
    sort: int | None = None


class RolePermissionsUpdate(BaseModel):
    permission_codes: list[str] = Field(default_factory=list)
