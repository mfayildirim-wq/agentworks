"""artifact_jobs.mode

Revision ID: 0022_artifact_job_mode
Revises: 0021_artifact_output_template
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0022_artifact_job_mode"
down_revision = "0021_artifact_output_template"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "artifact_jobs",
        sa.Column("mode", sa.String(20), nullable=False, server_default="update"),
    )


def downgrade() -> None:
    op.drop_column("artifact_jobs", "mode")
