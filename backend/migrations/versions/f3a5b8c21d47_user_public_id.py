"""user public id (globally unique, non-enumerable)

对外展示的用户编号：与自增主键解耦，随机 20 位、全局唯一。
存量用户先加可空列并回填（md5 随机串，格式 usr_ 加 20 位），再加唯一索引并置 NOT NULL。

Revision ID: f3a5b8c21d47
Revises: e2f4a91b7c35
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f3a5b8c21d47"
down_revision: str | None = "e2f4a91b7c35"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("public_id", sa.String(length=32), nullable=True))
    # 回填存量用户：md5(随机串 + 主键) 取 20 位，同批也不会重复
    op.execute(
        "UPDATE users SET public_id = 'usr_' || lower(substr(md5(random()::text || "
        "clock_timestamp()::text || id::text), 1, 20)) WHERE public_id IS NULL"
    )
    op.alter_column("users", "public_id", nullable=False)
    op.create_index(op.f("ix_users_public_id"), "users", ["public_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_public_id"), table_name="users")
    op.drop_column("users", "public_id")
