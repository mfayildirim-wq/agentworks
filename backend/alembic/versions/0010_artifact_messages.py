"""artifact_messages: Chat-Thread je Instanz (Dialog-Agent)

Revision ID: 0010_artifact_messages
Revises: 0009_user_api_keys
Create Date: 2026-06-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0010_artifact_messages"
down_revision = "0009_user_api_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "artifact_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "artifact_id",
            UUID(as_uuid=True),
            sa.ForeignKey("artifacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("artifact_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_artifact_messages_artifact_id", "artifact_messages", ["artifact_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_artifact_messages_artifact_id", table_name="artifact_messages")
    op.drop_table("artifact_messages")
