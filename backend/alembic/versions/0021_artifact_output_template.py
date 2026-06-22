"""artifacts.output_template

Revision ID: 0021_artifact_output_template
Revises: 0020_artifact_version_data
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0021_artifact_output_template"
down_revision = "0020_artifact_version_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "artifacts",
        sa.Column("output_template", sa.String(60), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("artifacts", "output_template")
