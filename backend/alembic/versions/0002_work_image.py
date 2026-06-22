"""work image_url

Revision ID: 0002_work_image
Revises: 0001_initial
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_work_image"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("works", sa.Column("image_url", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("works", "image_url")
