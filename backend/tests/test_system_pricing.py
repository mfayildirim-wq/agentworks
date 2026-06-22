from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from app.db.models import ModelPrice, User, WalletLedger
from app.db.session import SessionLocal
from app.services import model_pricing, roles


# --- Task 1: refresh_from_seed ----------------------------------------------


@pytest.mark.asyncio
async def test_refresh_resets_changed_price_to_seed():
    async with SessionLocal() as db:
        await model_pricing.ensure_seed(db)
        await db.commit()
        # Opus-Preis künstlich verbiegen
        await model_pricing.update_price(
            db, "claude-opus-4-8", Decimal("99"), Decimal("999"), by="hacker"
        )
        await db.commit()

        await model_pricing.refresh_from_seed(db)
        await db.commit()

        mp = await model_pricing.get(db, "claude-opus-4-8")
    assert mp.input_per_million_usd == Decimal("5.0")
    assert mp.output_per_million_usd == Decimal("25.0")
    assert mp.updated_by == "system-seed"


@pytest.mark.asyncio
async def test_refresh_creates_missing_seed_model():
    async with SessionLocal() as db:
        await db.execute(delete(ModelPrice).where(ModelPrice.model == "claude-opus-4-8"))
        await db.commit()
        assert await model_pricing.get(db, "claude-opus-4-8") is None

        await model_pricing.refresh_from_seed(db)
        await db.commit()

        mp = await model_pricing.get(db, "claude-opus-4-8")
    assert mp is not None
    assert mp.input_per_million_usd == Decimal("5.0")
    assert mp.output_per_million_usd == Decimal("25.0")


# --- Task 3: Endpoints (GOA-only) -------------------------------------------


@pytest.mark.asyncio
async def test_prices_forbidden_for_non_goa(client, monkeypatch):
    await client.get("/artifacts")
    monkeypatch.setattr(roles.settings, "admin_email", "someone-else@x.de")
    assert (await client.get("/system/prices")).status_code == 403
    assert (await client.post("/system/prices/refresh")).status_code == 403
    assert (await client.get("/system/billing/summary")).status_code == 403
    assert (await client.get("/system/users?q=x")).status_code == 403
    assert (await client.get(f"/system/users/{uuid4()}/consumption")).status_code == 403


@pytest.mark.asyncio
async def test_goa_lists_prices(client, monkeypatch):
    await client.get("/artifacts")
    monkeypatch.setattr(roles.settings, "admin_email", "test@local")
    r = await client.get("/system/prices")
    assert r.status_code == 200, r.text
    models = [p["model"] for p in r.json()]
    assert "claude-opus-4-8" in models


@pytest.mark.asyncio
async def test_goa_refresh_updates_opus(client, monkeypatch):
    await client.get("/artifacts")
    monkeypatch.setattr(roles.settings, "admin_email", "test@local")
    # erst verbiegen, dann refresh über Endpoint
    async with SessionLocal() as db:
        await model_pricing.ensure_seed(db)
        await db.commit()
        await model_pricing.update_price(
            db, "claude-opus-4-8", Decimal("1"), Decimal("2"), by="x"
        )
        await db.commit()

    r = await client.post("/system/prices/refresh")
    assert r.status_code == 200, r.text
    opus = next(p for p in r.json() if p["model"] == "claude-opus-4-8")
    assert float(opus["input_per_million_usd"]) == 5.0
    assert float(opus["output_per_million_usd"]) == 25.0

    async with SessionLocal() as db:
        mp = await model_pricing.get(db, "claude-opus-4-8")
    assert mp.input_per_million_usd == Decimal("5.0")


@pytest.mark.asyncio
async def test_goa_billing_summary_and_consumption(client, monkeypatch):
    await client.get("/artifacts")
    monkeypatch.setattr(roles.settings, "admin_email", "test@local")
    async with SessionLocal() as db:
        u = (await db.execute(
            select(User).where(User.google_sub == "test-user")
        )).scalars().first()
        db.add(WalletLedger(user_id=u.id, kind="charge", amount_usd=Decimal("-0.50"),
                            model="sumtest", tokens_in=7, tokens_out=3,
                            provider_cost_usd=Decimal("0.40")))
        await db.commit()
        uid = u.id

    r = await client.get("/system/billing/summary")
    assert r.status_code == 200, r.text
    body = r.json()
    row = next(m for m in body["models"] if m["model"] == "sumtest")
    assert float(row["einkauf_usd"]) == 0.40
    assert float(row["verkauf_usd"]) == 0.50
    assert float(row["gewinn_usd"]) == 0.10

    rc = await client.get(f"/system/users/{uid}/consumption")
    assert rc.status_code == 200, rc.text
    assert float(rc.json()["verkauf_usd"]) >= 0.50
