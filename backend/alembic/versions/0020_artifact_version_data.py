"""artifact_versions.data JSONB für Slot-DB

Revision ID: 0020_artifact_version_data
Revises: 0019_mcp_server_auth
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0020_artifact_version_data"
down_revision = "0019_mcp_server_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("artifact_versions", sa.Column("data", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("artifact_versions", "data")
