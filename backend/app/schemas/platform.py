from pydantic import BaseModel, Field


class TenantDomainCreate(BaseModel):
    """绑定域名。kind=subdomain 时 host 必须等于 <slug>.<tenant_base_domain>。"""

    host: str = Field(min_length=3, max_length=253)
    kind: str = Field(default='custom', pattern='^(subdomain|custom)$')


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    slug: str = Field(min_length=2, max_length=64, pattern="^[a-z0-9-]+$")
    email: str = Field(min_length=3, max_length=128)
    nickname: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=6, max_length=128)
