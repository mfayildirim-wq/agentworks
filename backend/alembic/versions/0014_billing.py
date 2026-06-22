"""billing wallet und Modellpreise"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0014_billing"
down_revision = "0013_artifact_files"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "balance_usd",
            sa.Numeric(12, 6),
            nullable=False,
            server_default="0",
        ),
    )

    op.create_table(
        "wallet_ledger",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("amount_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column("artifact_id", UUID(as_uuid=True), nullable=True),
        sa.Column("run_id", UUID(as_uuid=True), nullable=True),
        sa.Column("model", sa.String(80), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider_cost_usd", sa.Numeric(12, 6), nullable=False, server_default="0"),
        sa.Column("margin", sa.Numeric(4, 2), nullable=False, server_default="1.25"),
        sa.Column("description", sa.String(200), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_wallet_ledger_user_id", "wallet_ledger", ["user_id"])
    op.create_index("ix_wallet_ledger_artifact_id", "wallet_ledger", ["artifact_id"])
    op.create_index("ix_wallet_ledger_run_id", "wallet_ledger", ["run_id"])

    model_price = op.create_table(
        "model_price",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("label", sa.String(80), nullable=False, server_default=""),
        sa.Column("input_per_million_usd", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("output_per_million_usd", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_by", sa.String(255), nullable=True),
    )
    op.create_index("ix_model_price_model", "model_price", ["model"], unique=True)

    op.bulk_insert(
        model_price,
        [
            {
                "id": uuid.uuid4(),
                "provider": "anthropic",
                "model": "claude-haiku-4-5",
                "label": "Claude Haiku 4.5",
                "input_per_million_usd": 1.0,
                "output_per_million_usd": 5.0,
            },
            {
                "id": uuid.uuid4(),
                "provider": "anthropic",
                "model": "claude-sonnet-4-6",
                "label": "Claude Sonnet 4.6",
                "input_per_million_usd": 3.0,
                "output_per_million_usd": 15.0,
            },
            {
                "id": uuid.uuid4(),
                "provider": "anthropic",
                "model": "claude-opus-4-7",
                "label": "Claude Opus 4.7",
                "input_per_million_usd": 15.0,
                "output_per_million_usd": 75.0,
            },
            {
                "id": uuid.uuid4(),
                "provider": "openai",
                "model": "gpt-4o",
                "label": "GPT-4o",
                "input_per_million_usd": 2.5,
                "output_per_million_usd": 10.0,
            },
            {
                "id": uuid.uuid4(),
                "provider": "openai",
                "model": "gpt-4o-mini",
                "label": "GPT-4o mini",
                "input_per_million_usd": 0.15,
                "output_per_million_usd": 0.6,
            },
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_model_price_model", table_name="model_price")
    op.drop_table("model_price")
    op.drop_index("ix_wallet_ledger_run_id", table_name="wallet_ledger")
    op.drop_index("ix_wallet_ledger_artifact_id", table_name="wallet_ledger")
    op.drop_index("ix_wallet_ledger_user_id", table_name="wallet_ledger")
    op.drop_table("wallet_ledger")
    op.drop_column("users", "balance_usd")
