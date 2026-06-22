from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import AdminUser  # GOA-only (email == admin_email) → 403 sonst
from app.db.session import get_db
from app.schemas.billing import ModelPriceOut, PriceUpdate
from app.schemas.system import (
    BillingSummary,
    SystemKeysStatus,
    SystemKeysUpdate,
    UserConsumption,
    UserSearchRow,
)
from app.services import billing_report, model_pricing, system_keys

router = APIRouter(prefix="/system", tags=["system"])

_MARGIN = Decimal("1.30")


def _price_out(mp) -> ModelPriceOut:
    return ModelPriceOut(
        provider=mp.provider,
        model=mp.model,
        label=mp.label,
        input_per_million_usd=mp.input_per_million_usd,
        output_per_million_usd=mp.output_per_million_usd,
        portal_input_per_million_usd=mp.input_per_million_usd * _MARGIN,
        portal_output_per_million_usd=mp.output_per_million_usd * _MARGIN,
    )


@router.get("/keys", response_model=SystemKeysStatus)
async def get_system_keys(_goa: AdminUser, db: AsyncSession = Depends(get_db)):
    return SystemKeysStatus(**await system_keys.status(db))


@router.put("/keys", response_model=SystemKeysStatus)
async def put_system_keys(
    payload: SystemKeysUpdate, _goa: AdminUser, db: AsyncSession = Depends(get_db)
):
    st = await system_keys.set_keys(
        db,
        anthropic=payload.anthropic,
        openai=payload.openai,
        deepseek=payload.deepseek,
    )
    return SystemKeysStatus(**st)


# --- Modellpreise (GOA-only) -------------------------------------------------


@router.get("/prices", response_model=list[ModelPriceOut])
async def list_prices(_goa: AdminUser, db: AsyncSession = Depends(get_db)):
    return [_price_out(mp) for mp in await model_pricing.list_prices(db)]


@router.post("/prices/refresh", response_model=list[ModelPriceOut])
async def refresh_prices(_goa: AdminUser, db: AsyncSession = Depends(get_db)):
    """Setzt die DB-Preise auf die im Code gepflegten Festwerte zurück (kein Live-Abruf)."""
    rows = await model_pricing.refresh_from_seed(db)
    await db.commit()
    return [_price_out(mp) for mp in rows]


@router.put("/prices/{model}", response_model=ModelPriceOut)
async def update_price(
    model: str, body: PriceUpdate, admin: AdminUser, db: AsyncSession = Depends(get_db)
):
    mp = await model_pricing.update_price(
        db, model, body.input_per_million_usd, body.output_per_million_usd, admin.email
    )
    if mp is None:
        raise HTTPException(404, "Modell unbekannt")
    await db.commit()
    return _price_out(mp)


# --- Abrechnung & Nutzer-Verbrauch (GOA-only) --------------------------------


@router.get("/billing/summary", response_model=BillingSummary)
async def billing_summary(_goa: AdminUser, db: AsyncSession = Depends(get_db)):
    return BillingSummary(**await billing_report.model_summary(db))


@router.get("/users", response_model=list[UserSearchRow])
async def search_users(_goa: AdminUser, q: str = "", db: AsyncSession = Depends(get_db)):
    return await billing_report.search_users(db, q)


@router.get("/users/{user_id}/consumption", response_model=UserConsumption)
async def user_consumption(
    user_id: UUID, _goa: AdminUser, db: AsyncSession = Depends(get_db)
):
    return await billing_report.user_consumption(db, user_id)
