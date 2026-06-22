from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class ProfileOut(BaseModel):
    email: str
    name: str
    avatar_url: str | None = None
    # Benachrichtigungs-Kanäle.
    telegram_connected: bool = False
    notify_email: bool = True
    notify_telegram: bool = True
    # USD-Guthaben für Instanz-Läufe.
    balance_usd: Decimal = Decimal("0")
    # UI-Sprache.
    language: str = "de"


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    notify_email: bool | None = None
    notify_telegram: bool | None = None
    language: str | None = Field(default=None, pattern="^(de|en)$")


class TelegramLinkOut(BaseModel):
    token: str
    bot_username: str
