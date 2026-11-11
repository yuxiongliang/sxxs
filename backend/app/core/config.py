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
    cookie_secure: bool = False
    # Schema is owned by Alembic. Set to false to manage migrations out of band
    # (recommended once the service runs behind a release pipeline).
    db_auto_migrate: bool = True
    upload_dir: str = "uploads"
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

    # Rate limiting (Redis fixed window). Auth endpoints get a tighter budget.
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 600
    rate_limit_window_seconds: int = 60
    rate_limit_auth_requests: int = 20
    rate_limit_auth_window_seconds: int = 60
    cors_origins: list[str] = Field(
        default_factory=lambda: [
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
