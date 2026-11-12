"""attachment moderation and three way state

附件审核 + 三权分离（审核结论 / 强制下架 / 租户软删）。

手写而非直接用 autogenerate 产物，原因：
1. autogenerate 又带出了一批无关变更（departments/notifications/roles/system_settings
   的 server_default 调整，以及会删掉 users.role 外键的 drop_constraint）；
2. 直接 add_column(nullable=False) 在已有行的 attachments 上会失败，必须先 server_default；
3. 存量附件必须一律置 approved（否则上线瞬间所有商品图被判为待审）。

Revision ID: 9d98519e72d4
Revises: f3188a27e915
Create Date: 2026-11-12 09:36:34.473040
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9d98519e72d4"
down_revision: str | None = "f3188a27e915"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---- 1. 审核日志与去重缓存 ----
    op.create_table(
        "moderation_cache",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("review_kind", sa.String(length=16), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("categories", sa.JSON(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("checksum", "review_kind", name="uq_moderation_cache_checksum_kind"),
    )
    op.create_index(
        op.f("ix_moderation_cache_checksum"), "moderation_cache", ["checksum"], unique=False
    )

    op.create_table(
        "moderation_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("attachment_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("categories", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("raw", sa.JSON(), nullable=False),
        sa.Column("elapsed_ms", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["attachment_id"], ["attachments.id"], name="fk_moderation_logs_attachment_id"
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_id"], ["users.id"], name="fk_moderation_logs_reviewer_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_moderation_logs_attachment_id"), "moderation_logs", ["attachment_id"], unique=False
    )
    op.create_index(
        op.f("ix_moderation_logs_decision"), "moderation_logs", ["decision"], unique=False
    )

    # ---- 2. 附件新列（先给 server_default，否则已有行会违反 NOT NULL）----
    op.add_column("attachments", sa.Column("uploader_user_id", sa.Integer(), nullable=True))
    op.add_column(
        "attachments",
        sa.Column("uploader_role", sa.String(length=16), nullable=False, server_default="admin"),
    )
    op.add_column(
        "attachments",
        sa.Column("visibility", sa.String(length=16), nullable=False, server_default="tenant"),
    )
    # 存量附件一律视为已通过（历史数据默认可信）
    op.add_column(
        "attachments",
        sa.Column("review_status", sa.String(length=16), nullable=False, server_default="approved"),
    )
    op.add_column(
        "attachments",
        sa.Column("review_kind", sa.String(length=16), nullable=False, server_default="other"),
    )
    op.add_column(
        "attachments", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("attachments", sa.Column("review_provider", sa.String(length=32), nullable=True))
    op.add_column("attachments", sa.Column("reject_reason", sa.String(length=32), nullable=True))
    op.add_column(
        "attachments",
        sa.Column("admin_hidden", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("attachments", sa.Column("thumbnail_key", sa.String(length=255), nullable=True))
    op.add_column("attachments", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("attachments", sa.Column("deleted_by", sa.Integer(), nullable=True))

    # ---- 3. 存量数据回填 ----
    op.execute(
        "UPDATE attachments SET review_kind = 'image' WHERE category = 'image' AND review_kind = 'other'"
    )
    op.execute(
        "UPDATE attachments SET review_kind = 'video' WHERE category = 'video' AND review_kind = 'other'"
    )
    op.execute(
        "UPDATE attachments SET review_kind = 'document' WHERE category = 'document' AND review_kind = 'other'"
    )
    op.execute("UPDATE attachments SET reviewed_at = now() WHERE reviewed_at IS NULL")
    # 回填完成后清掉这些库级默认值：默认值只由模型（Python 侧）提供，
    # 否则 alembic 会认为库与模型不一致（test_no_pending_autogenerate_diff 会挂）。
    for column in ("uploader_role", "visibility", "review_kind", "admin_hidden", "review_status"):
        op.alter_column("attachments", column, server_default=None)

    # ---- 4. 索引与外键 ----
    op.create_index(
        op.f("ix_attachments_uploader_user_id"), "attachments", ["uploader_user_id"], unique=False
    )
    op.create_index(
        op.f("ix_attachments_uploader_role"), "attachments", ["uploader_role"], unique=False
    )
    op.create_index(op.f("ix_attachments_visibility"), "attachments", ["visibility"], unique=False)
    op.create_index(
        op.f("ix_attachments_review_status"), "attachments", ["review_status"], unique=False
    )
    op.create_index(
        op.f("ix_attachments_admin_hidden"), "attachments", ["admin_hidden"], unique=False
    )
    op.create_index(op.f("ix_attachments_deleted_at"), "attachments", ["deleted_at"], unique=False)
    op.create_foreign_key(
        "fk_attachments_uploader_user_id", "attachments", "users", ["uploader_user_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_attachments_deleted_by", "attachments", "users", ["deleted_by"], ["id"]
    )

    # ---- 5. 平台自有资源：tenant_id 允许为空 ----
    op.alter_column(
        "attachments",
        "tenant_id",
        existing_type=sa.INTEGER(),
        nullable=True,
        server_default=None,
    )


def downgrade() -> None:
    op.alter_column(
        "attachments",
        "tenant_id",
        existing_type=sa.INTEGER(),
        nullable=False,
        server_default="1",
    )
    op.drop_constraint("fk_attachments_deleted_by", "attachments", type_="foreignkey")
    op.drop_constraint("fk_attachments_uploader_user_id", "attachments", type_="foreignkey")
    for index in (
        "ix_attachments_deleted_at",
        "ix_attachments_admin_hidden",
        "ix_attachments_review_status",
        "ix_attachments_visibility",
        "ix_attachments_uploader_role",
        "ix_attachments_uploader_user_id",
    ):
        op.drop_index(op.f(index), table_name="attachments")
    for column in (
        "deleted_by",
        "deleted_at",
        "thumbnail_key",
        "admin_hidden",
        "reject_reason",
        "review_provider",
        "reviewed_at",
        "review_kind",
        "review_status",
        "visibility",
        "uploader_role",
        "uploader_user_id",
    ):
        op.drop_column("attachments", column)
    op.drop_index(op.f("ix_moderation_logs_decision"), table_name="moderation_logs")
    op.drop_index(op.f("ix_moderation_logs_attachment_id"), table_name="moderation_logs")
    op.drop_table("moderation_logs")
    op.drop_index(op.f("ix_moderation_cache_checksum"), table_name="moderation_cache")
    op.drop_table("moderation_cache")
