"""setting inheritance source and platform policy

配置继承所需的两个表的字段：
1. `system_settings.source` —— 租户选择 inherit / override，存量一律 inherit；
   同时去掉 `tenant_id` 的库级默认值（漏传应报错，而不是静默落到 demo 租户）。
2. `platform_settings.policy_locked / version` —— 平台锁定开关与配置版本号。

手写而非 autogenerate：autogenerate 会顺带产出 departments/notifications/roles 等
表的无关 server_default 调整，以及会删掉 users.role 外键的 drop_constraint。

Revision ID: 56954f0550ae
Revises: 9d98519e72d4
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "56954f0550ae"
down_revision: str | None = "9d98519e72d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---- 1) 租户配置来源 ----
    op.add_column(
        "system_settings",
        sa.Column("source", sa.String(length=16), nullable=False, server_default="inherit"),
    )
    op.add_column("system_settings", sa.Column("updated_by", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_system_settings_source"), "system_settings", ["source"], unique=False)
    op.create_foreign_key(
        "fk_system_settings_updated_by", "system_settings", "users", ["updated_by"], ["id"]
    )
    # 存量一律 inherit：平台未启用该类配置时会自动回落租户自己的历史配置，
    # 因此不会因为「平台还没填」而让全站支付/邮件立刻不可用。
    op.execute("UPDATE system_settings SET source = 'inherit' WHERE source IS NULL")
    # 默认值只由模型提供，保证 alembic diff 干净
    op.alter_column("system_settings", "source", server_default=None)
    # 去掉 tenant_id 的库级默认值
    op.alter_column(
        "system_settings",
        "tenant_id",
        existing_type=sa.INTEGER(),
        server_default=None,
        existing_nullable=False,
    )

    # ---- 2) 平台配置的锁定与版本 ----
    op.add_column(
        "platform_settings",
        sa.Column("policy_locked", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "platform_settings",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.alter_column("platform_settings", "policy_locked", server_default=None)
    op.alter_column("platform_settings", "version", server_default=None)


def downgrade() -> None:
    op.drop_column("platform_settings", "version")
    op.drop_column("platform_settings", "policy_locked")
    op.alter_column(
        "system_settings",
        "tenant_id",
        existing_type=sa.INTEGER(),
        server_default="1",
        existing_nullable=False,
    )
    op.drop_constraint("fk_system_settings_updated_by", "system_settings", type_="foreignkey")
    op.drop_index(op.f("ix_system_settings_source"), table_name="system_settings")
    op.drop_column("system_settings", "updated_by")
    op.drop_column("system_settings", "source")
