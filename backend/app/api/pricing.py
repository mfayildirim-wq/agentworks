from __future__ import annotations

from decimal import Decimal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import AdminUser
from app.core.settings import get_settings
from app.db.session import get_db
from app.schemas.billing import ModelPriceOut, PriceUpdate
from app.services import model_pricing

settings = get_settings()
router = APIRouter(prefix="/pricing", tags=["pricing"])

_MARGIN = Decimal("1.30")


def _to_out(mp) -> ModelPriceOut:
    return ModelPriceOut(
        provider=mp.provider,
        model=mp.model,
        label=mp.label,
        input_per_million_usd=mp.input_per_million_usd,
        output_per_million_usd=mp.output_per_million_usd,
        portal_input_per_million_usd=mp.input_per_million_usd * _MARGIN,
        portal_output_per_million_usd=mp.output_per_million_usd * _MARGIN,
    )


@router.get("", response_model=list[ModelPriceOut])
async def list_prices(db: AsyncSession = Depends(get_db)):
    return [_to_out(mp) for mp in await model_pricing.list_prices(db)]


@router.put("/{model}", response_model=ModelPriceOut)
async def update_price(
    model: str, body: PriceUpdate, admin: AdminUser, db: AsyncSession = Depends(get_db)
):
    mp = await model_pricing.update_price(
        db, model, body.input_per_million_usd, body.output_per_million_usd, admin.email
    )
    if mp is None:
        raise HTTPException(404, "Modell unbekannt")
    await db.commit()
    return _to_out(mp)


@router.post("/refresh")
async def refresh_prices(admin: AdminUser):
    """Lädt Preis-Vorschläge aus settings.pricing_source_url (JSON). Schreibt NICHT."""
    if not settings.pricing_source_url:
        raise HTTPException(400, "Keine pricing_source_url konfiguriert.")
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(settings.pricing_source_url)
            r.raise_for_status()
            return {"proposals": r.json()}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Preisquelle nicht erreichbar: {exc}") from exc
