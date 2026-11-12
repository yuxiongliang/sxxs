"""platform admin flag and platform settings

平台端与租户端拆分所需的两项数据库改动：
1. users.is_platform_admin —— 平台账号身份标识，与租户成员身份解耦；
2. platform_settings —— 平台级配置（无 tenant_id）。

注意：autogenerate 原本还带出了一批无关变更（server_default 调整、索引重建、
以及会删掉 users.role → roles.code 外键的 drop_constraint），已全部剔除。

Revision ID: f3188a27e915
Revises: 827234440f6b
Create Date: 2026-11-11 23:41:27.640472
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f3188a27e915"
down_revision: str | None = "827234440f6b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_platform_admin", sa.Boolean(), server_default="false", nullable=False),
    )
    op.create_index(
        op.f("ix_users_is_platform_admin"), "users", ["is_platform_admin"], unique=False
    )

    op.create_table(
        "platform_settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_platform_settings_category"), "platform_settings", ["category"], unique=True
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_platform_settings_category"), table_name="platform_settings")
    op.drop_table("platform_settings")
    op.drop_index(op.f("ix_users_is_platform_admin"), table_name="users")
    op.drop_column("users", "is_platform_admin")
