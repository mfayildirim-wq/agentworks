"""output_mode default -> hinzufuegen + Bestand heben

Revision ID: 0032_output_mode_default
Revises: 0031_artifact_output_mode
"""
from alembic import op
import sqlalchemy as sa

revision = "0032_output_mode_default"
down_revision = "0031_artifact_output_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("artifacts", "output_mode", server_default="hinzufuegen")
    # Bestands-Artefakte mit altem Default auf den neuen Standard heben.
    op.execute("UPDATE artifacts SET output_mode='hinzufuegen' WHERE output_mode='ueberschreiben'")
    # Tote Sektions-Modi auf den Tab-Standard mappen.
    op.execute("UPDATE artifacts SET output_mode='hinzufuegen' WHERE output_mode IN ('oben','unten','neuer_tab')")


def downgrade() -> None:
    # Hinweis: lossy — die in upgrade() auf 'hinzufuegen' gehobenen Bestandszeilen
    # (vormals 'ueberschreiben'/'oben'/'unten'/'neuer_tab') werden NICHT rekonstruiert.
    # Ein sauberes Rollback setzt zusätzlich den Branch auf den 0031-Stand zurück.
    op.alter_column("artifacts", "output_mode", server_default="ueberschreiben")
