"""artifact_connections: verschlüsselte SFTP-Verbindung je Instanz"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0016_artifact_connections"
down_revision = "0015_artifact_message_files"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "artifact_connections",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("artifact_id", UUID(as_uuid=True),
                  sa.ForeignKey("artifacts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="sftp"),
        sa.Column("host", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("port", sa.Integer(), nullable=False, server_default="22"),
        sa.Column("username", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("password_encrypted", sa.Text(), nullable=False, server_default=""),
        sa.Column("remote_path", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("artifact_id", "kind", name="uq_artifact_connection_kind"),
    )
    op.create_index("ix_artifact_connections_artifact_id", "artifact_connections", ["artifact_id"])
    op.create_index("ix_artifact_connections_owner_id", "artifact_connections", ["owner_id"])


def downgrade() -> None:
    op.drop_table("artifact_connections")
