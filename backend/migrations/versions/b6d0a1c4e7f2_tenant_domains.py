"""tenant domains (B6 host resolution)

租户域名表：Host → tenant 的唯一事实源。

- 子域（{slug}.{tenant_base_domain}）归我们所有，创建即 active；
- 客户自带域名必须 TXT 验证通过才 active，否则任何人都能把别人的域名指过来。

host 上的唯一索引是硬约束：两个租户绝不能抢同一个 host。

Revision ID: b6d0a1c4e7f2
Revises: c9d2e3f4a5b6
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b6d0a1c4e7f2"
down_revision: str | None = "c9d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tenant_domains",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("host", sa.String(length=253), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("verify_token", sa.String(length=64), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_primary",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_tenant_domains_tenant"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tenant_domains_tenant_id"), "tenant_domains", ["tenant_id"])
    op.create_index(op.f("ix_tenant_domains_host"), "tenant_domains", ["host"], unique=True)
    op.create_index(op.f("ix_tenant_domains_status"), "tenant_domains", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_tenant_domains_status"), table_name="tenant_domains")
    op.drop_index(op.f("ix_tenant_domains_host"), table_name="tenant_domains")
    op.drop_index(op.f("ix_tenant_domains_tenant_id"), table_name="tenant_domains")
    op.drop_table("tenant_domains")
