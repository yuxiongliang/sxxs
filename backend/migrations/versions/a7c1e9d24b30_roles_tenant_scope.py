"""roles 增加 tenant_id：把「系统共享角色」和「租户自建角色」分开

Revision ID: a7c1e9d24b30
Revises: f3a5b8c21d47
Create Date: 2026-11-13

背景：`roles` 原本是全库共享表，租户控制台的角色管理因此能看到、也能改
**别的租户**的自定义角色，以及所有租户共享的系统角色（viewer / tenant_admin …）。

改法：`tenant_id` 为 NULL 表示系统共享角色（所有租户只读可见）；
非 NULL 表示某个租户自建的角色（只有该租户可见、可改）。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "a7c1e9d24b30"
down_revision = "f3a5b8c21d47"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("roles", sa.Column("tenant_id", sa.Integer(), nullable=True))
    op.create_index("ix_roles_tenant_id", "roles", ["tenant_id"])
    op.create_foreign_key(
        "fk_roles_tenant_id_tenants",
        "roles",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )
    # 现有角色全部视为系统共享角色（tenant_id 留空），保持各租户现状不变。


def downgrade() -> None:
    op.drop_constraint("fk_roles_tenant_id_tenants", "roles", type_="foreignkey")
    op.drop_index("ix_roles_tenant_id", table_name="roles")
    op.drop_column("roles", "tenant_id")
