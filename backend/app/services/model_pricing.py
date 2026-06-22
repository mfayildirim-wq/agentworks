"""Provider-Preise (ModelPrice) lesen, seeden, aktualisieren."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ModelPrice

_SEED = [
    ("anthropic", "claude-haiku-4-5", "Claude Haiku 4.5", "1.0", "5.0"),
    ("anthropic", "claude-sonnet-4-6", "Claude Sonnet 4.6", "3.0", "15.0"),
    ("anthropic", "claude-opus-4-8", "Claude Opus 4.8", "5.0", "25.0"),
    ("openai", "gpt-4o", "GPT-4o", "2.5", "10.0"),
    ("openai", "gpt-4o-mini", "GPT-4o mini", "0.15", "0.6"),
    ("deepseek", "deepseek-chat", "DeepSeek Chat", "0.27", "1.10"),
]


async def ensure_seed(db: AsyncSession) -> None:
    """Legt fehlende Standard-Modelle an (idempotent). Für Tests/Erststart."""
    existing = set((await db.execute(select(ModelPrice.model))).scalars().all())
    for provider, model, label, pin, pout in _SEED:
        if model not in existing:
            db.add(ModelPrice(
                provider=provider, model=model, label=label,
                input_per_million_usd=Decimal(pin), output_per_million_usd=Decimal(pout),
            ))


async def refresh_from_seed(db: AsyncSession) -> list[ModelPrice]:
    """Setzt alle Seed-Modelle auf die im Code gepflegten Festwerte zurück.

    Fehlende Modelle werden via ``ensure_seed`` angelegt, vorhandene auf den Festwert
    überschrieben (``updated_by="system-seed"``). Der Commit obliegt dem Aufrufer.
    """
    await ensure_seed(db)
    await db.flush()
    for provider, model, label, pin, pout in _SEED:
        await update_price(db, model, Decimal(pin), Decimal(pout), by="system-seed")
    rows = (await db.execute(
        select(ModelPrice).order_by(ModelPrice.provider, ModelPrice.model)
    )).scalars().all()
    return list(rows)


async def list_prices(db: AsyncSession) -> list[ModelPrice]:
    # Auch frische DBs (z. B. Test-DB ohne Migration-Seed) bekommen die Standardpreise.
    await ensure_seed(db)
    await db.commit()
    rows = (await db.execute(
        select(ModelPrice).order_by(ModelPrice.provider, ModelPrice.model)
    )).scalars().all()
    return list(rows)


async def provider_for(db: AsyncSession, model: str) -> str | None:
    """Provider eines bekannten Modells (Modell ist die Wahrheitsquelle für den Provider —
    so kann ein veraltetes/falsches provider-Feld am Agenten nicht falsch routen)."""
    mp = await get(db, model)
    return mp.provider if mp else None


async def get(db: AsyncSession, model: str) -> ModelPrice | None:
    return (await db.execute(
        select(ModelPrice).where(ModelPrice.model == model)
    )).scalar_one_or_none()


async def update_price(
    db: AsyncSession, model: str, pin: Decimal, pout: Decimal, by: str
) -> ModelPrice | None:
    mp = await get(db, model)
    if mp is None:
        return None
    mp.input_per_million_usd = pin
    mp.output_per_million_usd = pout
    mp.updated_by = by
    return mp


async def price_for(db: AsyncSession, model: str) -> tuple[Decimal, Decimal]:
    """(input_per_million, output_per_million); unbekannt => (0,0)."""
    mp = await get(db, model)
    if mp is None:
        return (Decimal("0"), Decimal("0"))
    return (mp.input_per_million_usd, mp.output_per_million_usd)
