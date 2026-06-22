"""Visibility-Enum um 'draft' erweitern (owner-only Entwurf)

Revision ID: 0034_visibility_draft
Revises: 0033_user_deepseek_key
"""
from alembic import op

revision = "0034_visibility_draft"
down_revision = "0033_user_deepseek_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PG16: ADD VALUE ist transaktionssicher; IF NOT EXISTS macht es idempotent.
    op.execute("ALTER TYPE visibility ADD VALUE IF NOT EXISTS 'draft'")


def downgrade() -> None:
    # Enum-Werte lassen sich in PostgreSQL nicht einfach entfernen — bewusst No-op.
    pass
