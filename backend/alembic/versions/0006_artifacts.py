"""artifacts + artifact_versions (Phase 5c)

Revision ID: 0006_artifacts
Revises: 0005_work_loop_config
Create Date: 2026-06-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006_artifacts"
down_revision = "0005_work_loop_config"
branch_labels = None
depends_on = None

template_output_enum = postgresql.ENUM(
    "html", "markdown", "json", name="template_output", create_type=False
)
visibility_enum = postgresql.ENUM(
    "private", "unlisted", "public", name="visibility", create_type=False
)


def upgrade() -> None:
    op.create_table(
        "artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(200), nullable=False, server_default=""),
        sa.Column("output_type", template_output_enum, nullable=False, server_default="html"),
        sa.Column("visibility", visibility_enum, nullable=False, server_default="unlisted"),
        sa.Column("current_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("file_path", sa.String(512), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("owner_id", "agent_id", name="uq_artifacts_owner_agent"),
    )
    op.create_table(
        "artifact_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "artifact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("artifacts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("work_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("artifact_id", "version_no", name="uq_artifact_versions_no"),
    )


def downgrade() -> None:
    op.drop_table("artifact_versions")
    op.drop_table("artifacts")
