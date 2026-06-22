"""friends + visibility.friends + artifact default private

Revision ID: 0024_friends_and_visibility
Revises: 0023_artifact_chat_summary
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0024_friends_and_visibility"
down_revision = "0023_artifact_chat_summary"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enum-Wert außerhalb der Transaktion ergänzen (PG-Anforderung).
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE visibility ADD VALUE IF NOT EXISTS 'friends'")
    op.create_table(
        "friendships",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("requester_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("addressee_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("requester_id", "addressee_id", name="uq_friendship_pair"),
    )
    op.create_index("ix_friendships_requester_id", "friendships", ["requester_id"])
    op.create_index("ix_friendships_addressee_id", "friendships", ["addressee_id"])
    op.alter_column("artifacts", "visibility", server_default="private")


def downgrade() -> None:
    op.alter_column("artifacts", "visibility", server_default="unlisted")
    op.drop_index("ix_friendships_addressee_id", "friendships")
    op.drop_index("ix_friendships_requester_id", "friendships")
    op.drop_table("friendships")
    # Enum-Wert wird nicht entfernt (PG kann das nicht einfach).
