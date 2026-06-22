"""artifact_schedules: zeitgesteuerte Selbst-Aktualisierung (Phase 5e)

Revision ID: 0008_artifact_schedules
Revises: 0007_artifact_instances
Create Date: 2026-06-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008_artifact_schedules"
down_revision = "0007_artifact_instances"
branch_labels = None
depends_on = None

cadence_enum = postgresql.ENUM("hourly", "daily", "weekly", name="schedule_cadence")
status_enum = postgresql.ENUM("active", "paused", "completed", name="schedule_status")
completion_enum = postgresql.ENUM("once", "until", "recurring", name="schedule_completion")


def upgrade() -> None:
    bind = op.get_bind()
    cadence_enum.create(bind, checkfirst=True)
    status_enum.create(bind, checkfirst=True)
    completion_enum.create(bind, checkfirst=True)

    op.create_table(
        "artifact_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "artifact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("artifacts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "cadence",
            postgresql.ENUM(name="schedule_cadence", create_type=False),
            nullable=False,
            server_default="daily",
        ),
        sa.Column("cron_expr", sa.String(120), nullable=False),
        sa.Column("refresh_instruction", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "completion_mode",
            postgresql.ENUM(name="schedule_completion", create_type=False),
            nullable=False,
            server_default="recurring",
        ),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "status",
            postgresql.ENUM(name="schedule_status", create_type=False),
            nullable=False,
            server_default="active",
        ),
        sa.Column("fail_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("run_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("work_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("artifact_id", name="uq_artifact_schedules_artifact"),
    )


def downgrade() -> None:
    op.drop_table("artifact_schedules")
    bind = op.get_bind()
    completion_enum.drop(bind, checkfirst=True)
    status_enum.drop(bind, checkfirst=True)
    cadence_enum.drop(bind, checkfirst=True)
