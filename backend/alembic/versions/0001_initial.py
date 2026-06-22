"""Initial schema (users, agents, works, runs, messages, logs, ratings, workflows, cron, rag)

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


# postgresql.ENUM (nicht sa.Enum): nur dieser respektiert create_type=False.
# Die Typen werden unten EINMAL explizit per .create(checkfirst=True) angelegt; sonst
# emittiert jedes create_table ein zusätzliches, unbedingtes CREATE TYPE → DuplicateObject.
visibility_enum = postgresql.ENUM(
    "private", "unlisted", "public", name="visibility", create_type=False
)
run_status_enum = postgresql.ENUM(
    "pending", "running", "completed", "failed", name="run_status", create_type=False
)
run_mode_enum = postgresql.ENUM(
    "single", "group", "swarm", "graph", name="run_mode", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))

    visibility_enum.create(bind, checkfirst=True)
    run_status_enum.create(bind, checkfirst=True)
    run_mode_enum.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("google_sub", sa.String(64), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False, server_default=""),
        sa.Column("avatar_url", sa.String(512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("role", sa.String(120), nullable=False, server_default=""),
        sa.Column("domain", sa.String(120), nullable=False, server_default=""),
        sa.Column("avatar_url", sa.String(512), nullable=True),
        sa.Column(
            "visibility", visibility_enum, nullable=False, server_default="private"
        ),
        sa.Column("price_per_run", sa.Float, nullable=False, server_default="0"),
        sa.Column("current_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_agents_owner_id", "agents", ["owner_id"])
    op.create_index("ix_agents_visibility", "agents", ["visibility"])
    op.create_index("ix_agents_domain", "agents", ["domain"])
    op.create_index("ix_agents_name", "agents", ["name"])

    op.create_table(
        "agent_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("system_prompt", sa.Text, nullable=False, server_default=""),
        sa.Column("model", sa.String(80), nullable=False, server_default="claude-sonnet-4-6"),
        sa.Column("temperature", sa.Float, nullable=False, server_default="0.7"),
        sa.Column("tools", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("config", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_agent_versions_agent_id", "agent_versions", ["agent_id"])

    op.create_table(
        "agent_skills",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("skill", sa.String(80), nullable=False),
        sa.UniqueConstraint("agent_id", "skill"),
    )
    op.create_index("ix_agent_skills_skill", "agent_skills", ["skill"])

    op.create_table(
        "works",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("goal", sa.Text, nullable=False),
        sa.Column("expected_outcome", sa.Text, nullable=False, server_default=""),
        sa.Column("initial_message", sa.Text, nullable=False, server_default=""),
        sa.Column("mode", run_mode_enum, nullable=False, server_default="single"),
        sa.Column(
            "visibility", visibility_enum, nullable=False, server_default="private"
        ),
        sa.Column("max_turns", sa.Integer, nullable=False, server_default="12"),
        sa.Column("max_tokens", sa.Integer, nullable=False, server_default="50000"),
        sa.Column("workflow_graph", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_works_owner_id", "works", ["owner_id"])

    op.create_table(
        "work_agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "work_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("works.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_versions.id"),
            nullable=True,
        ),
        sa.Column("role_in_work", sa.String(80), nullable=False, server_default=""),
        sa.Column("handoff_targets", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("order_idx", sa.Integer, nullable=False, server_default="0"),
        sa.UniqueConstraint("work_id", "agent_id"),
    )

    op.create_table(
        "work_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "work_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("works.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", run_status_enum, nullable=False, server_default="pending"),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_tokens_in", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_tokens_out", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_cost", sa.Float, nullable=False, server_default="0"),
        sa.Column("result", postgresql.JSONB, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
    )
    op.create_index("ix_work_runs_work_id", "work_runs", ["work_id"])
    op.create_index("ix_work_runs_status", "work_runs", ["status"])

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("work_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id"),
            nullable=True,
        ),
        sa.Column("agent_name", sa.String(120), nullable=False, server_default=""),
        sa.Column("role", sa.String(40), nullable=False, server_default="assistant"),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("tokens_in", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float, nullable=False, server_default="0"),
        sa.Column(
            "ts",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_messages_run_id", "messages", ["run_id"])
    op.create_index("ix_messages_ts", "messages", ["ts"])

    op.create_table(
        "logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("work_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("level", sa.String(16), nullable=False, server_default="info"),
        sa.Column("type", sa.String(40), nullable=False, server_default="event"),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "ts",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_logs_run_id", "logs", ["run_id"])

    op.create_table(
        "ratings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stars", sa.Integer, nullable=False),
        sa.Column("comment", sa.Text, nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("agent_id", "user_id"),
    )

    op.create_table(
        "rag_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("chunk", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    bind.execute(sa.text("ALTER TABLE rag_documents ADD COLUMN embedding vector(1024)"))
    op.create_index("ix_rag_documents_agent_id", "rag_documents", ["agent_id"])

    op.create_table(
        "memory_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "cron_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "work_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("works.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("cron_expr", sa.String(120), nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_cost_usd", sa.Float, nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_cron_jobs_owner_id", "cron_jobs", ["owner_id"])


def downgrade() -> None:
    op.drop_table("cron_jobs")
    op.drop_table("memory_entries")
    op.drop_table("rag_documents")
    op.drop_table("ratings")
    op.drop_table("logs")
    op.drop_table("messages")
    op.drop_table("work_runs")
    op.drop_table("work_agents")
    op.drop_table("works")
    op.drop_table("agent_skills")
    op.drop_table("agent_versions")
    op.drop_table("agents")
    op.drop_table("users")
    run_mode_enum.drop(op.get_bind(), checkfirst=True)
    run_status_enum.drop(op.get_bind(), checkfirst=True)
    visibility_enum.drop(op.get_bind(), checkfirst=True)
