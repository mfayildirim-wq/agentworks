"""provider + api_key_encrypted

Revision ID: 0003_provider_apikey
Revises: 0002_work_image
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_provider_apikey"
down_revision = "0002_work_image"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_versions",
        sa.Column("provider", sa.String(length=20), nullable=False, server_default="anthropic"),
    )
    op.add_column(
        "agents",
        sa.Column("api_key_encrypted", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agents", "api_key_encrypted")
    op.drop_column("agent_versions", "provider")
