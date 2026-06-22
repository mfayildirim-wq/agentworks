"""artifact_connections: kind-agnostisch (config JSONB + secret_encrypted)"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0017_artifact_connection_config"
down_revision = "0016_artifact_connections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("artifact_connections",
                  sa.Column("config", JSONB(), nullable=False, server_default="{}"))
    op.add_column("artifact_connections",
                  sa.Column("secret_encrypted", sa.Text(), nullable=False, server_default=""))
    for col in ("host", "port", "username", "password_encrypted", "remote_path"):
        op.drop_column("artifact_connections", col)


def downgrade() -> None:
    op.add_column("artifact_connections", sa.Column("remote_path", sa.String(512), nullable=False, server_default=""))
    op.add_column("artifact_connections", sa.Column("password_encrypted", sa.Text(), nullable=False, server_default=""))
    op.add_column("artifact_connections", sa.Column("username", sa.String(255), nullable=False, server_default=""))
    op.add_column("artifact_connections", sa.Column("port", sa.Integer(), nullable=False, server_default="22"))
    op.add_column("artifact_connections", sa.Column("host", sa.String(255), nullable=False, server_default=""))
    op.drop_column("artifact_connections", "secret_encrypted")
    op.drop_column("artifact_connections", "config")
