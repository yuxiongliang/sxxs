"""plans 删除 quotas 列：套餐不再按商品/成员配额计量

Revision ID: b8d2f4a61c07
Revises: a7c1e9d24b30
Create Date: 2026-11-13

平台端已经不再维护「商品数 / 成员数」配额（改卖终身买断、不限量），
后端却还留着列、接口字段、强制校验和租户端展示。本迁移把列删掉，
与代码侧（模型/接口/服务/种子）同步收口。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "b8d2f4a61c07"
down_revision = "a7c1e9d24b30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("plans", "quotas")


def downgrade() -> None:
    op.add_column("plans", sa.Column("quotas", sa.JSON(), nullable=True))
