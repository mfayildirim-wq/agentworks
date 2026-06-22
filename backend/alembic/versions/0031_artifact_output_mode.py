"""artifacts.output_mode

Revision ID: 0031_artifact_output_mode
Revises: 0030_channel_sessions
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0031_artifact_output_mode"
down_revision = "0030_channel_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("artifacts", sa.Column("output_mode", sa.String(16), nullable=False,
                  server_default="ueberschreiben"))


def downgrade() -> None:
    op.drop_column("artifacts", "output_mode")
