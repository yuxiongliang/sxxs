"""notification templates

平台/租户两类通知模板。scope 区分品牌归属：
  platform → 平台发给租户（品牌=平台）
  tenant   → 租户发给买家（品牌=租户）

Revision ID: b7c1d2e3f4a5
Revises: f5bf19255082
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7c1d2e3f4a5"
down_revision: str | None = "f5bf19255082"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_templates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("variables", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("mandatory", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
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
        sa.UniqueConstraint("scope", "code", name="uq_notification_template_scope_code"),
    )
    op.create_index(
        op.f("ix_notification_templates_scope"), "notification_templates", ["scope"], unique=False
    )
    op.create_index(
        op.f("ix_notification_templates_code"), "notification_templates", ["code"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_notification_templates_code"), table_name="notification_templates")
    op.drop_index(op.f("ix_notification_templates_scope"), table_name="notification_templates")
    op.drop_table("notification_templates")
