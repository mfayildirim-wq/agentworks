"""User.language (UI-Sprache de|en)

Revision ID: 0035_user_language
Revises: 0034_visibility_draft
"""
from alembic import op
import sqlalchemy as sa

revision = "0035_user_language"
down_revision = "0034_visibility_draft"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("language", sa.String(length=2),
                                     nullable=False, server_default="de"))


def downgrade() -> None:
    op.drop_column("users", "language")
