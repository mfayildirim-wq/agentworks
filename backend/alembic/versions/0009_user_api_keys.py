"""users: eigene AI-API-Keys (verschlüsselt)

Revision ID: 0009_user_api_keys
Revises: 0008_artifact_schedules
Create Date: 2026-06-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_user_api_keys"
down_revision = "0008_artifact_schedules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("openai_key_encrypted", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("anthropic_key_encrypted", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "anthropic_key_encrypted")
    op.drop_column("users", "openai_key_encrypted")
