from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TopUpRequest(BaseModel):
    amount_usd: Decimal = Field(gt=0, le=1000)


class LedgerItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kind: str
    amount_usd: Decimal
    artifact_id: UUID | None = None
    app_name: str | None = None
    model: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    description: str = ""
    created_at: datetime


class WalletOut(BaseModel):
    balance_usd: Decimal
    ledger: list[LedgerItem]
    topup_mode: str = "free"


class InstanceUsageOut(BaseModel):
    artifact_id: UUID
    title: str
    icon: str | None = None
    total_usd: Decimal
    runs: int
    last_at: datetime | None = None


class ModelPriceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider: str
    model: str
    label: str
    input_per_million_usd: Decimal
    output_per_million_usd: Decimal
    portal_input_per_million_usd: Decimal
    portal_output_per_million_usd: Decimal


class PriceUpdate(BaseModel):
    input_per_million_usd: Decimal = Field(ge=0)
    output_per_million_usd: Decimal = Field(ge=0)


class TopUpOut(BaseModel):
    mode: str
    checkout_url: str | None = None
    wallet: WalletOut | None = None


class ConfirmRequest(BaseModel):
    # Stripe-Checkout-Session-IDs sind immer `cs_test_…` / `cs_live_…` — strikt validieren,
    # damit beliebige Strings nicht die Stripe-API anstoßen können (Enumerations-Schutz).
    session_id: str = Field(min_length=4, max_length=120, pattern=r"^cs_[A-Za-z0-9_]+$")
