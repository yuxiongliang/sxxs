from pydantic import BaseModel, Field


class TenantBrandOut(BaseModel):
    tenant_id: int
    slug: str
    name: str
    display_name: str
    logo_url: str | None = None
    favicon_url: str | None = None
    theme_color: str | None = None


class TenantBrandUpdate(BaseModel):
    """租户维护自己的站点品牌。平台可覆盖（后续在平台端做）。"""

    display_name: str | None = Field(default=None, max_length=64)
    logo_url: str | None = Field(default=None, max_length=512)
    favicon_url: str | None = Field(default=None, max_length=512)
    theme_color: str | None = Field(default=None, max_length=16)
