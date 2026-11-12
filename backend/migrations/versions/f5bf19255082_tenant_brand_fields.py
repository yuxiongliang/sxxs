"""tenant brand fields

租户站点品牌：全站名称 / logo / favicon / 主题色。

放 tenants 表而不是 system_settings：登录页、邮件模板、404 页在「配置尚未
加载」时就要用到品牌，依赖 settings 会导致首屏空白。

四个字段全部 nullable，无需 backfill（display_name 为空时由接口回落到 name）。

Revision ID: f5bf19255082
Revises: 56954f0550ae
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f5bf19255082"
down_revision: str | None = "56954f0550ae"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("display_name", sa.String(length=64), nullable=True))
    op.add_column("tenants", sa.Column("logo_url", sa.String(length=512), nullable=True))
    op.add_column("tenants", sa.Column("favicon_url", sa.String(length=512), nullable=True))
    op.add_column("tenants", sa.Column("theme_color", sa.String(length=16), nullable=True))


def downgrade() -> None:
    for column in ("theme_color", "favicon_url", "logo_url", "display_name"):
        op.drop_column("tenants", column)
