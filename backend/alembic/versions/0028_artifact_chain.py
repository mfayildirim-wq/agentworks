"""artifacts.next_artifact_id + chain_auto
Revision ID: 0028_artifact_chain
Revises: 0027_topup_mode_and_external_ref
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0028_artifact_chain"
down_revision = "0027_topup_mode_and_external_ref"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("artifacts", sa.Column("next_artifact_id", UUID(as_uuid=True), nullable=True))
    op.add_column("artifacts", sa.Column("chain_auto", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_foreign_key("fk_artifacts_next_artifact", "artifacts", "artifacts",
                          ["next_artifact_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.drop_constraint("fk_artifacts_next_artifact", "artifacts", type_="foreignkey")
    op.drop_column("artifacts", "chain_auto")
    op.drop_column("artifacts", "next_artifact_id")
