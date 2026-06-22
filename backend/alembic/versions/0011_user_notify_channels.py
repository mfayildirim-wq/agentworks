"""users: Benachrichtigungs-Kanäle (Telegram + Prefs)

Revision ID: 0011_user_notify_channels
Revises: 0010_artifact_messages
Create Date: 2026-06-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011_user_notify_channels"
down_revision = "0010_artifact_messages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("telegram_chat_id", sa.String(length=32), nullable=True))
    op.add_column("users", sa.Column("telegram_link_token", sa.String(length=64), nullable=True))
    op.add_column(
        "users",
        sa.Column("notify_email", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "users",
        sa.Column("notify_telegram", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("users", "notify_telegram")
    op.drop_column("users", "notify_email")
    op.drop_column("users", "telegram_link_token")
    op.drop_column("users", "telegram_chat_id")
