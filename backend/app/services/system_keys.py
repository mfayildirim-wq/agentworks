"""System-Keys (Anthropic, OpenAI, DeepSeek) auf dem GOA-Nutzer.

Die Keys liegen verschlüsselt (Fernet) auf genau dem Nutzer-Datensatz, dessen
E-Mail `settings.admin_email` ist (GOA). Instanz-Läufe nutzen diese System-Keys;
fehlt ein DB-Key, greift der `.env`-Fallback (`settings.<provider>_api_key`).
Keys werden NIE im Klartext geloggt oder zurückgegeben.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import crypto
from app.core.settings import get_settings
from app.db.models import User

settings = get_settings()

_PROVIDERS = ("anthropic", "openai", "deepseek")
_FIELD = {
    "anthropic": "anthropic_key_encrypted",
    "openai": "openai_key_encrypted",
    "deepseek": "deepseek_key_encrypted",
}
_ENV = {
    "anthropic": "anthropic_api_key",
    "openai": "openai_api_key",
    "deepseek": "deepseek_api_key",
}


async def _goa(db: AsyncSession) -> User | None:
    """Der GOA-/System-Nutzer (E-Mail == settings.admin_email)."""
    return (
        await db.execute(select(User).where(User.email == settings.admin_email))
    ).scalar_one_or_none()


def _env_key(provider: str) -> str | None:
    return getattr(settings, _ENV[provider], None) or None


async def system_key_for(db: AsyncSession, provider: str) -> str | None:
    """Verschlüsselter GOA-Feld-Key (entschlüsselt), sonst Env-Fallback, sonst None."""
    if provider not in _FIELD:
        provider = "anthropic"
    goa = await _goa(db)
    if goa is not None:
        enc = getattr(goa, _FIELD[provider])
        if enc:
            return crypto.decrypt(enc)
    return _env_key(provider)


async def status(db: AsyncSession) -> dict[str, bool]:
    """Pro Provider: True, wenn GOA-Feld ODER Env gesetzt ist (nie Klartext)."""
    goa = await _goa(db)
    out: dict[str, bool] = {}
    for p in _PROVIDERS:
        has_db = bool(getattr(goa, _FIELD[p])) if goa is not None else False
        out[p] = has_db or bool(_env_key(p))
    return out


async def set_keys(
    db: AsyncSession,
    *,
    anthropic: str | None = None,
    openai: str | None = None,
    deepseek: str | None = None,
) -> dict[str, bool]:
    """Setzt System-Keys auf dem GOA-Nutzer.

    None oder Leerstring => Feld unverändert behalten; sonst verschlüsselt speichern.
    """
    goa = await _goa(db)
    if goa is None:
        return await status(db)
    incoming = {"anthropic": anthropic, "openai": openai, "deepseek": deepseek}
    for provider, value in incoming.items():
        if value is None:
            continue
        value = value.strip()
        if value == "":
            continue
        setattr(goa, _FIELD[provider], crypto.encrypt(value))
    await db.commit()
    await db.refresh(goa)
    return await status(db)
