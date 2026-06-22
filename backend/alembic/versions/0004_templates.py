"""Templates + template_runs (Phase 5a)

Revision ID: 0004_templates
Revises: 0003_provider_apikey
Create Date: 2026-06-03
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0004_templates"
down_revision = "0003_provider_apikey"
branch_labels = None
depends_on = None

template_output_enum = postgresql.ENUM(
    "html", "markdown", "json", name="template_output", create_type=False
)
# Bestehende Enums nur referenzieren (create_type=False → kein CREATE TYPE):
visibility_enum = postgresql.ENUM(
    "private", "unlisted", "public", name="visibility", create_type=False
)
run_mode_enum = postgresql.ENUM(
    "single", "group", "swarm", "graph", name="run_mode", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    template_output_enum.create(bind, checkfirst=True)

    op.create_table(
        "templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("category", sa.String(80), nullable=False, server_default="", index=True),
        sa.Column("visibility", visibility_enum, nullable=False, server_default="private"),
        sa.Column(
            "input_schema",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("output_type", template_output_enum, nullable=False, server_default="html"),
        sa.Column("mode", run_mode_enum, nullable=False, server_default="single"),
        sa.Column(
            "config",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("max_iterations", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("max_cost_usd", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("success_criteria", postgresql.JSONB(), nullable=True),
        sa.Column("image_url", sa.String(512), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    op.create_table(
        "template_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("templates.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "inputs", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "work_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("works.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


def downgrade() -> None:
    op.drop_table("template_runs")
    op.drop_table("templates")
    template_output_enum.drop(op.get_bind(), checkfirst=True)
