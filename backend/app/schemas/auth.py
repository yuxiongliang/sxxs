from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)
    tenant_id: int | None = None


class RegisterRequest(BaseModel):
    tenant_slug: str = Field(min_length=1, max_length=64)
    email: str = Field(min_length=3, max_length=128)
    nickname: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class TenantSummary(BaseModel):
    id: int
    name: str
    slug: str
    status: str
    roles: list[str] = Field(default_factory=list)


class AuthUser(BaseModel):
    id: int
    username: str
    nickname: str
    email: str
    avatar: str | None = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: AuthUser
    tenants: list[TenantSummary]
    current_tenant: TenantSummary
    roles: list[str]
    permissions: list[str]
    permission_version: int


class MeResponse(BaseModel):
    user: AuthUser
    tenants: list[TenantSummary]
    current_tenant: TenantSummary
    roles: list[str]
    permissions: list[str]
    permission_version: int


class SwitchTenantRequest(BaseModel):
    tenant_id: int
