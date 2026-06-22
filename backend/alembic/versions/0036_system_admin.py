"""is_system_admin (Systemadmin = erster Nutzer) + Prod-GOA migrieren

Revision ID: 0036_system_admin
Revises: 0035_user_language
"""
from alembic import op
import sqlalchemy as sa

revision = "0036_system_admin"
down_revision = "0035_user_language"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_system_admin", sa.Boolean(),
                                     nullable=False, server_default="false"))
    # Bestehende Installation: der ÄLTESTE (zuerst installierende) Nutzer wird Systemadmin,
    # sofern noch keiner gesetzt ist. Frische Installation (0 Nutzer) → No-op; der erste
    # Login setzt das Flag dann beim Anlegen.
    op.execute(
        "UPDATE users SET is_system_admin = true WHERE id = ("
        "  SELECT id FROM users ORDER BY created_at ASC LIMIT 1"
        ") AND NOT EXISTS (SELECT 1 FROM users WHERE is_system_admin = true)"
    )


def downgrade() -> None:
    op.drop_column("users", "is_system_admin")
