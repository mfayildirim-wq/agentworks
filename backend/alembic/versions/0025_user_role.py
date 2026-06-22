"""users.role
Revision ID: 0025_user_role
Revises: 0024_friends_and_visibility
"""
from __future__ import annotations
import sqlalchemy as sa
from alembic import op
revision = "0025_user_role"
down_revision = "0024_friends_and_visibility"
branch_labels = None
depends_on = None
def upgrade() -> None:
    op.add_column("users", sa.Column("role", sa.String(16), nullable=False, server_default=""))
def downgrade() -> None:
    op.drop_column("users", "role")
