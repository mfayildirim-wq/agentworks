"""templates.publish_status + publish_note
Revision ID: 0026_template_publish_status
Revises: 0025_user_role
"""
from __future__ import annotations
import sqlalchemy as sa
from alembic import op
revision = "0026_template_publish_status"
down_revision = "0025_user_role"
branch_labels = None
depends_on = None
def upgrade() -> None:
    op.add_column("templates", sa.Column("publish_status", sa.String(16), nullable=False, server_default=""))
    op.add_column("templates", sa.Column("publish_note", sa.Text(), nullable=False, server_default=""))
def downgrade() -> None:
    op.drop_column("templates", "publish_note")
    op.drop_column("templates", "publish_status")
