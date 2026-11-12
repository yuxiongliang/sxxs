"""plan duration in months

套餐加「时长（月）」：管理员在平台端填 N 个月，订阅窗口按 N × 30 天算。
lifetime/custom 不使用该字段，所以可空、无需回填。

Revision ID: e2f4a91b7c35
Revises: d91b7c3e5a04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e2f4a91b7c35"
down_revision: str | None = "d91b7c3e5a04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("plans", sa.Column("duration_months", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("plans", "duration_months")
