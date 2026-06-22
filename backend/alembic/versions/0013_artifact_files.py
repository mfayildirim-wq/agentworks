"""artifact_files: im Instanz-Chat hochgeladene Dateien"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0013_artifact_files"
down_revision = "0012_artifact_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "artifact_files",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "artifact_id",
            UUID(as_uuid=True),
            sa.ForeignKey("artifacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "owner_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("url", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("content_type", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_artifact_files_artifact_id", "artifact_files", ["artifact_id"])
    op.create_index("ix_artifact_files_owner_id", "artifact_files", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_artifact_files_owner_id", table_name="artifact_files")
    op.drop_index("ix_artifact_files_artifact_id", table_name="artifact_files")
    op.drop_table("artifact_files")
