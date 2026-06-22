"""Work.loop_config (Phase 5b — Ziel-Loop)

Revision ID: 0005_work_loop_config
Revises: 0004_templates
Create Date: 2026-06-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_work_loop_config"
down_revision = "0004_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("works", sa.Column("loop_config", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("works", "loop_config")
