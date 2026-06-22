"""users.topup_mode + wallet_ledger.external_ref
Revision ID: 0027_topup_mode_and_external_ref
Revises: 0026_template_publish_status
"""
from __future__ import annotations
import sqlalchemy as sa
from alembic import op
revision = "0027_topup_mode_and_external_ref"
down_revision = "0026_template_publish_status"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("users", sa.Column("topup_mode", sa.String(8), nullable=False, server_default="free"))
    op.add_column("wallet_ledger", sa.Column("external_ref", sa.String(120), nullable=True))
    # Unique-Index: Idempotenz der Stripe-Gutschrift auch bei gleichzeitigen Confirm-Calls
    # (Postgres lässt mehrere NULLs in einem Unique-Index zu → topup/charge-Zeilen unberührt).
    op.create_index("ix_wallet_ledger_external_ref", "wallet_ledger", ["external_ref"], unique=True)

def downgrade() -> None:
    op.drop_index("ix_wallet_ledger_external_ref", table_name="wallet_ledger")
    op.drop_column("wallet_ledger", "external_ref")
    op.drop_column("users", "topup_mode")
