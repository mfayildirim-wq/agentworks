from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class SystemKeysStatus(BaseModel):
    """Nur ob ein Key hinterlegt ist — NIE Klartext."""

    anthropic: bool = False
    openai: bool = False
    deepseek: bool = False


class SystemKeysUpdate(BaseModel):
    """Optionale Keys. Leerstring/None => Feld unverändert behalten."""

    anthropic: str | None = None
    openai: str | None = None
    deepseek: str | None = None


class BillingRow(BaseModel):
    """Eine Zeile der Abrechnungs-Summary (je Modell oder Gesamtzeile)."""

    model: str | None = None
    runs: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    einkauf_usd: Decimal = Decimal("0")
    verkauf_usd: Decimal = Decimal("0")
    gewinn_usd: Decimal = Decimal("0")


class BillingSummary(BaseModel):
    models: list[BillingRow] = []
    total: BillingRow


class UserConsumption(BaseModel):
    user_id: UUID
    tokens_in: int = 0
    tokens_out: int = 0
    einkauf_usd: Decimal = Decimal("0")
    verkauf_usd: Decimal = Decimal("0")
    gewinn_usd: Decimal = Decimal("0")
    runs: int = 0
    topups_usd: Decimal = Decimal("0")
    saldo_usd: Decimal = Decimal("0")


class UserSearchRow(BaseModel):
    user_id: UUID
    email: str
    name: str = ""
    saldo_usd: Decimal = Decimal("0")
    verkauf_usd: Decimal = Decimal("0")
