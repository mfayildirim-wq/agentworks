"""Abrechenbare Modelle (Claude/OpenAI) aus der Preis-Tabelle."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import model_pricing


async def list_models(db: AsyncSession) -> list[dict]:
    return [
        {"value": mp.model, "label": mp.label, "group": mp.provider.capitalize()}
        for mp in await model_pricing.list_prices(db)
    ]
