from __future__ import annotations
from uuid import uuid4
import pytest
from decimal import Decimal
from sqlalchemy import select
from app.db.session import SessionLocal
from app.db.models import User
from app.services import billing, roles


class _U:
    def __init__(self, email, role="", topup_mode="free"):
        self.email = email; self.role = role; self.topup_mode = topup_mode

def test_effective_topup_mode(monkeypatch):
    monkeypatch.setattr(roles.settings, "admin_email", "boss@x.de")
    assert billing.effective_topup_mode(_U("u@x.de", topup_mode="free")) == "free"
    assert billing.effective_topup_mode(_U("u@x.de", topup_mode="real")) == "real"
    assert billing.effective_topup_mode(_U("u@x.de", role="admin", topup_mode="real")) == "real"  # kein Admin-Auto-Free mehr
    assert billing.effective_topup_mode(_U("boss@x.de", topup_mode="real")) == "real"  # Systemadmin auch kein Auto-Free

@pytest.mark.asyncio
async def test_set_topup_mode(client, monkeypatch):
    monkeypatch.setattr(roles.settings, "admin_email", "boss@x.de")
    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = User(email=f"p-{uuid4()}@x.de", google_sub=str(uuid4()), name="PayBob")
        db.add(u); await db.commit()
        assert await roles.set_topup_mode(db, u.id, "real") is True
        assert (await db.get(User, u.id)).topup_mode == "real"
        assert await roles.set_topup_mode(db, u.id, "quatsch") is False
        goa = User(email="boss@x.de", google_sub=str(uuid4()), name="Boss")
        db.add(goa); await db.commit()
        assert await roles.set_topup_mode(db, goa.id, "real") is False

@pytest.mark.asyncio
async def test_top_up_external_ref(client):
    # Frischer Nutzer — NICHT der geteilte Auth-Test-Nutzer (sonst akkumuliert dessen
    # Guthaben über die session-scoped DB und stört absolute Saldo-Asserts anderer Tests).
    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = User(email=f"ext-{uuid4()}@x.de", google_sub=str(uuid4()), name="ExtRef")
        db.add(u); await db.flush()
        led = await billing.top_up(db, u, Decimal("5"), external_ref="sess_123")
        await db.commit()
        assert led.external_ref == "sess_123"

def test_stripe_is_configured(monkeypatch):
    from app.services import stripe_pay
    monkeypatch.setattr(stripe_pay.settings, "stripe_secret_key", "")
    assert stripe_pay.is_configured() is False
    monkeypatch.setattr(stripe_pay.settings, "stripe_secret_key", "sk_test_x")
    assert stripe_pay.is_configured() is True
