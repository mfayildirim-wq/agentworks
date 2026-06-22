from __future__ import annotations


async def test_wallet_topup_and_read(client):
    r = await client.post("/wallet/topup", json={"amount_usd": 10})
    assert r.status_code == 200, r.text
    w = (await client.get("/wallet")).json()
    assert float(w["balance_usd"]) == 10.0
    assert any(p["kind"] == "topup" for p in w["ledger"])


async def test_wallet_topup_rejects_bad_amount(client):
    assert (await client.post("/wallet/topup", json={"amount_usd": 0})).status_code == 422
    assert (await client.post("/wallet/topup", json={"amount_usd": 99999})).status_code == 422


async def test_topup_free_credits_immediately(client):
    r = await client.post("/wallet/topup", json={"amount_usd": 7})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "free" and body["checkout_url"] is None
    assert float(body["wallet"]["balance_usd"]) >= 7.0
    assert body["wallet"]["topup_mode"] == "free"


async def test_topup_real_returns_checkout_url(client, monkeypatch):
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.db.models import User
    from app.services import stripe_pay
    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        u.topup_mode = "real"; await db.commit()
    monkeypatch.setattr(stripe_pay, "is_configured", lambda: True)
    monkeypatch.setattr(stripe_pay, "create_checkout_session", lambda *a, **k: "https://checkout.stripe.test/sess_abc")
    r = await client.post("/wallet/topup", json={"amount_usd": 12})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "real" and body["checkout_url"].startswith("https://checkout.stripe.test")
    assert body["wallet"] is None
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        u.topup_mode = "free"; await db.commit()


async def test_topup_real_without_stripe_503(client, monkeypatch):
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.db.models import User
    from app.services import stripe_pay
    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        u.topup_mode = "real"; await db.commit()
    monkeypatch.setattr(stripe_pay, "is_configured", lambda: False)
    r = await client.post("/wallet/topup", json={"amount_usd": 5})
    assert r.status_code == 503
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        u.topup_mode = "free"; await db.commit()


async def test_stripe_confirm_idempotent(client, monkeypatch):
    from decimal import Decimal
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.db.models import User
    from app.services import stripe_pay
    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        uid = str(u.id); before = float(u.balance_usd or 0)
    monkeypatch.setattr(stripe_pay, "retrieve_paid_amount", lambda sid: (True, Decimal("20"), uid))
    r1 = await client.post("/wallet/stripe/confirm", json={"session_id": "cs_test_xyz"})
    assert r1.status_code == 200
    r2 = await client.post("/wallet/stripe/confirm", json={"session_id": "cs_test_xyz"})
    assert r2.status_code == 200
    w = (await client.get("/wallet")).json()
    assert abs(float(w["balance_usd"]) - (before + 20.0)) < 1e-6


async def test_stripe_confirm_foreign_session_no_credit(client, monkeypatch):
    from decimal import Decimal
    from app.services import stripe_pay
    await client.get("/artifacts")
    w0 = (await client.get("/wallet")).json()
    monkeypatch.setattr(stripe_pay, "retrieve_paid_amount", lambda sid: (True, Decimal("99"), "fremde-user-id"))
    r = await client.post("/wallet/stripe/confirm", json={"session_id": "cs_test_foreign"})
    assert r.status_code == 200
    w1 = (await client.get("/wallet")).json()
    assert float(w1["balance_usd"]) == float(w0["balance_usd"])


async def test_stripe_confirm_rejects_non_stripe_session_id(client):
    # Beliebige Strings (kein cs_-Präfix) → 422, Stripe wird gar nicht erst angestoßen.
    r = await client.post("/wallet/stripe/confirm", json={"session_id": "evil-probe"})
    assert r.status_code == 422
