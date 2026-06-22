"""channel_sessions
Revision ID: 0030_channel_sessions
Revises: 0029_drop_local_models
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "0030_channel_sessions"
down_revision = "0029_drop_local_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "channel_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("channel_user_id", sa.String(64), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("active_artifact_id", UUID(as_uuid=True),
                  sa.ForeignKey("artifacts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("pending", JSONB, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("channel", "channel_user_id", name="uq_channel_user"),
    )


def downgrade() -> None:
    op.drop_table("channel_sessions")
