"""user deepseek_key_encrypted -> System-Keys (deepseek)

Revision ID: 0033_user_deepseek_key
Revises: 0032_output_mode_default
"""
from alembic import op
import sqlalchemy as sa

revision = "0033_user_deepseek_key"
down_revision = "0032_output_mode_default"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("deepseek_key_encrypted", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "deepseek_key_encrypted")
