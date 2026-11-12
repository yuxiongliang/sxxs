from pydantic import BaseModel, Field


class TenantDomainCreate(BaseModel):
    """绑定域名。kind=subdomain 时 host 必须等于 <slug>.<tenant_base_domain>。"""

    host: str = Field(min_length=3, max_length=253)
    kind: str = Field(default="custom", pattern="^(subdomain|custom)$")


class ServiceCategoryCreate(BaseModel):
    """平台级业务类目。commission_bps 是万分比：500 = 5%。"""

    code: str = Field(min_length=2, max_length=32, pattern="^[a-z0-9-]+$")
    name: str = Field(min_length=1, max_length=64)
    description: str = Field(default="", max_length=255)
    commission_bps: int = Field(default=0, ge=0, le=10000)
    sort: int = Field(default=0, ge=0)


class ServiceCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=255)
    commission_bps: int | None = Field(default=None, ge=0, le=10000)
    status: str | None = Field(default=None, pattern="^(active|archived)$")
    sort: int | None = Field(default=None, ge=0)


class TenantCategoryAssign(BaseModel):
    """给租户归类；传 null 表示取消归类（撤销后不再抽佣）。"""

    service_category_id: int | None = None


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    slug: str = Field(min_length=2, max_length=64, pattern="^[a-z0-9-]+$")
    email: str = Field(min_length=3, max_length=128)
    nickname: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    # 开通时就归到某个业务类目（决定抽佣比例）；不传表示暂未分类。
    service_category_id: int | None = None
