"""mcp_server auth fields + widen artifact_connections.kind

Revision ID: 0019_mcp_server_auth
Revises: 0018_mcp_server
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0019_mcp_server_auth"
down_revision = "0018_mcp_server"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mcp_server",
        sa.Column("auth_header", sa.String(80), nullable=False, server_default="Authorization"),
    )
    op.add_column(
        "mcp_server",
        sa.Column("auth_value_template", sa.String(200), nullable=False, server_default="Bearer {secret}"),
    )
    op.add_column(
        "mcp_server",
        sa.Column("secret_label", sa.String(120), nullable=False, server_default="Token / API-Key"),
    )
    op.alter_column(
        "artifact_connections", "kind",
        existing_type=sa.String(16), type_=sa.String(80), existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "artifact_connections", "kind",
        existing_type=sa.String(80), type_=sa.String(16), existing_nullable=False,
    )
    op.drop_column("mcp_server", "secret_label")
    op.drop_column("mcp_server", "auth_value_template")
    op.drop_column("mcp_server", "auth_header")
