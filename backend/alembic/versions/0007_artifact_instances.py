"""artifact instances: drop owner/agent unique, add inputs (Phase 5d)

Revision ID: 0007_artifact_instances
Revises: 0006_artifacts
Create Date: 2026-06-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_artifact_instances"
down_revision = "0006_artifacts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Mehrere Instanzen pro (Owner, Agent) erlauben.
    op.drop_constraint("uq_artifacts_owner_agent", "artifacts", type_="unique")
    # Nutzereingaben der Instanz (Bestandszeilen bekommen {}).
    op.add_column(
        "artifacts",
        sa.Column(
            "inputs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("artifacts", "inputs")
    op.create_unique_constraint(
        "uq_artifacts_owner_agent", "artifacts", ["owner_id", "agent_id"]
    )
