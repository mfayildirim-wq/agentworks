"""artifact_messages.file_ids: angehängte Datei-IDs je Nachricht (für Vision)"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0015_artifact_message_files"
down_revision = "0014_billing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "artifact_messages",
        sa.Column("file_ids", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("artifact_messages", "file_ids")
