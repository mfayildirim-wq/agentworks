"""Bestehende ollama/lokale Agenten auf Claude Haiku umbiegen (keine lokalen Modelle mehr)
Revision ID: 0029_drop_local_models
Revises: 0028_artifact_chain
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0029_drop_local_models"
down_revision = "0028_artifact_chain"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Lokale Modelle werden nicht mehr genutzt — Bestands-Agenten auf den neuen
    # Cloud-Default (Claude Haiku) heben, damit sie tool-fähig laufen statt lokal.
    op.execute(sa.text(
        "UPDATE agent_versions SET provider = 'anthropic', model = 'claude-haiku-4-5' "
        "WHERE provider = 'ollama' OR model LIKE 'qwen%'"
    ))


def downgrade() -> None:
    # Datenrückführung nicht sinnvoll (alte Modellwahl ist verloren) — bewusst No-Op.
    pass
