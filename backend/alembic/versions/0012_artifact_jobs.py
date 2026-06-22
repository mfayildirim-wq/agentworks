"""artifact_jobs: mehrere Jobs pro Instanz; Backfill aus artifact_schedules

Revision ID: 0012_artifact_jobs
Revises: 0011_user_notify_channels
Create Date: 2026-06-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.services.artifact_jobs import BACKFILL_SCHEDULES_SQL

revision = "0012_artifact_jobs"
down_revision = "0011_user_notify_channels"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "artifact_jobs",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("artifact_id", sa.UUID(as_uuid=True),
                  sa.ForeignKey("artifacts.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("owner_id", sa.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("instruction", sa.Text(), nullable=False, server_default=""),
        sa.Column("trigger_kind", sa.String(length=16), nullable=False, server_default="recurring"),
        sa.Column("cadence", sa.String(length=16), nullable=True),
        sa.Column("cron_expr", sa.String(length=120), nullable=True),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active", index=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_id", sa.UUID(as_uuid=True),
                  sa.ForeignKey("work_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("run_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fail_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notify_email", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notify_telegram", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notify_chat", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.String(length=16), nullable=False, server_default="agent"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.execute(BACKFILL_SCHEDULES_SQL)


def downgrade() -> None:
    op.drop_table("artifact_jobs")
