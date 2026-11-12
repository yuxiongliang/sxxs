from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Ant Design Pro Admin API"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+asyncpg://yuxiongliang@127.0.0.1:5433/ant_design_pro_admin"
    redis_url: str = "redis://127.0.0.1:6379/0"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    refresh_cookie_name: str = "antd_pro_refresh"
    # 平台端用独立的 cookie 名：开发环境两个前端共用 localhost，
    # 复用同一个 cookie 会让两边登录互相覆盖对方的 refresh token。
    platform_refresh_cookie_name: str = "sxxs_platform_refresh"
    cookie_secure: bool = False
    # Schema is owned by Alembic. Set to false to manage migrations out of band
    # (recommended once the service runs behind a release pipeline).
    db_auto_migrate: bool = True
    environment: str = "development"
    upload_dir: str = "uploads"
    # 附件静态目录只允许开发环境直出；生产一律走鉴权下载 / 签名 URL。
    serve_uploads_static: bool = True
    public_base_url: str = "http://127.0.0.1:9000"
    max_upload_size: int = 50 * 1024 * 1024

    # SaaS billing lifecycle. The background scheduler invoices expired terms and
    # downgrades tenants that never pay; disable it when a release pipeline runs
    # POST /api/v1/platform/billing/run-cycle instead.
    billing_scheduler_enabled: bool = True
    billing_scheduler_interval_seconds: int = 3600
    billing_grace_days: int = 7

    # 经营看板按业务时区切分自然日。用 UTC 切日会让每天有 8 小时的「今天」算错。
    business_timezone: str = "Asia/Shanghai"

    # ---- B6 自定义域名（Host → 租户）----
    # 租户子域后缀：\{slug\}.{tenant_base_domain}。留空表示不自动建子域。
    tenant_base_domain: str = ""
    # 平台控制台自己的域名：命中它时不做租户解析（平台端没有租户概念）。
    platform_host: str = ""
    # 域名所有权校验的 TXT 解析提供者：none（不校验，停在 pending）/ dns / static（测试）。
    domain_verify_provider: str = "none"
    # Host 解析不出来时是否回落到 ?tenant= 或默认租户。
    # 线上必须关闭：把「不认识的域名」静默当成 demo 站，会让租户误以为域名已生效。
    tenant_host_fallback: bool = True

    # Rate limiting (Redis fixed window). Auth endpoints get a tighter budget.
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 600
    rate_limit_window_seconds: int = 60
    rate_limit_auth_requests: int = 20
    rate_limit_auth_window_seconds: int = 60
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            # 租户控制台 dev 端口（8001 留给平台端，见 package.json 的 PORT=8010）
            "http://localhost:8010",
            "http://127.0.0.1:8010",
            # 平台端控制台
            "http://localhost:8001",
            "http://127.0.0.1:8001",
            # 历史端口，保留以免旧环境打不开
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://localhost:8002",
            "http://127.0.0.1:8002",
        ]
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def upload_path(self) -> Path:
        path = Path(self.upload_dir).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
