"""mcp_server: DB-gestützter MCP-Katalog (vom Admin verwaltet) + Demo-Server"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0018_mcp_server"
down_revision = "0017_artifact_connection_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mcp_server",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("server_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("description", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("transport", sa.String(length=20), nullable=False, server_default="streamable_http"),
        sa.Column("url", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("requires_credential", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.UniqueConstraint("server_id", name="uq_mcp_server_server_id"),
    )
    op.create_index("ix_mcp_server_server_id", "mcp_server", ["server_id"], unique=True)
    op.execute(
        "INSERT INTO mcp_server (id, server_id, name, description, transport, url, "
        "requires_credential, enabled, updated_at) VALUES "
        "(gen_random_uuid(), 'demo-everything', 'MCP Demo (everything-Referenzserver)', "
        "'Demo-Server zum Testen der MCP-Anbindung (Rechner-Tools).', 'streamable_http', "
        "'http://mcp-demo:8080/mcp', false, true, now())"
    )


def downgrade() -> None:
    op.drop_index("ix_mcp_server_server_id", table_name="mcp_server")
    op.drop_table("mcp_server")
