"""service categories (platform-level tenant classification with commission)

平台级业务类目：租户归到哪个类目，以及平台按多少比例向该租户抽佣。
与商品类目 categories 无关 —— 那张表是租户自己的橱窗分类。

tenants.service_category_id 可空：未分类 = 不抽佣，运营可以后补；
不为存量租户编造归属，避免账务口径凭空多出一笔抽佣。

Revision ID: c7e2f4a91b38
Revises: b6d0a1c4e7f2
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7e2f4a91b38"
down_revision: str | None = "b6d0a1c4e7f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "service_categories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("commission_bps", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("sort", sa.Integer(), nullable=False),
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
        op.f("ix_service_categories_code"), "service_categories", ["code"], unique=True
    )
    op.create_index(op.f("ix_service_categories_status"), "service_categories", ["status"])

    op.add_column("tenants", sa.Column("service_category_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_tenants_service_category_id"), "tenants", ["service_category_id"]
    )
    op.create_foreign_key(
        "fk_tenants_service_category",
        "tenants",
        "service_categories",
        ["service_category_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_tenants_service_category", "tenants", type_="foreignkey")
    op.drop_index(op.f("ix_tenants_service_category_id"), table_name="tenants")
    op.drop_column("tenants", "service_category_id")
    op.drop_index(op.f("ix_service_categories_status"), table_name="service_categories")
    op.drop_index(op.f("ix_service_categories_code"), table_name="service_categories")
    op.drop_table("service_categories")
