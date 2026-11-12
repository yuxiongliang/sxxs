"""plan lifetime and custom term windows

套餐只剩两种非周期形态（永久买断 / 管理员自定义起止的档期），需要给 plans 加
starts_at / ends_at。买断与档期套餐一律 trial_days=0（schema 层校验），所以这里
不需要回填任何数据。

Revision ID: d91b7c3e5a04
Revises: c7e2f4a91b38
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d91b7c3e5a04"
down_revision: str | None = "c7e2f4a91b38"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("plans", sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("plans", sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("plans", "ends_at")
    op.drop_column("plans", "starts_at")
