"""artifacts.chat_summary + summarized_count

Revision ID: 0023_artifact_chat_summary
Revises: 0022_artifact_job_mode
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0023_artifact_chat_summary"
down_revision = "0022_artifact_job_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("artifacts", sa.Column("chat_summary", sa.Text(), nullable=False, server_default=""))
    op.add_column("artifacts", sa.Column("summarized_count", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("artifacts", "summarized_count")
    op.drop_column("artifacts", "chat_summary")
