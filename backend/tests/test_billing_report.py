from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.models import User, WalletLedger
from app.db.session import SessionLocal
from app.services import billing_report


async def _mk_user(db) -> User:
    u = User(email=f"u-{uuid4()}@x.de", google_sub=str(uuid4()), name="Berta Test")
    db.add(u)
    await db.flush()
    return u


@pytest.mark.asyncio
async def test_model_summary_aggregates_purchase_sale_profit():
    async with SessionLocal() as db:
        u = await _mk_user(db)
        # zwei charges für modell "mx": Einkauf 0.10+0.20, Verkauf 0.125+0.25
        db.add(WalletLedger(user_id=u.id, kind="charge", amount_usd=Decimal("-0.125"),
                            model="mx", tokens_in=100, tokens_out=50,
                            provider_cost_usd=Decimal("0.10")))
        db.add(WalletLedger(user_id=u.id, kind="charge", amount_usd=Decimal("-0.25"),
                            model="mx", tokens_in=200, tokens_out=80,
                            provider_cost_usd=Decimal("0.20")))
        # topup darf NICHT in die charge-Summary einfließen
        db.add(WalletLedger(user_id=u.id, kind="topup", amount_usd=Decimal("10")))
        await db.commit()

        out = await billing_report.model_summary(db)

    row = next(r for r in out["models"] if r["model"] == "mx")
    assert row["runs"] == 2
    assert row["tokens_in"] == 300
    assert row["tokens_out"] == 130
    assert row["einkauf_usd"] == Decimal("0.30")
    assert row["verkauf_usd"] == Decimal("0.375")
    assert row["gewinn_usd"] == Decimal("0.075")
    # Gesamtzeile enthält mindestens diese mx-Werte (DB ist geteilt → >=)
    assert out["total"]["einkauf_usd"] >= Decimal("0.30")
    assert out["total"]["verkauf_usd"] >= Decimal("0.375")
    assert out["total"]["gewinn_usd"] == out["total"]["verkauf_usd"] - out["total"]["einkauf_usd"]


@pytest.mark.asyncio
async def test_user_consumption():
    async with SessionLocal() as db:
        u = await _mk_user(db)
        db.add(WalletLedger(user_id=u.id, kind="topup", amount_usd=Decimal("5")))
        db.add(WalletLedger(user_id=u.id, kind="charge", amount_usd=Decimal("-0.40"),
                            model="mc", tokens_in=10, tokens_out=5,
                            provider_cost_usd=Decimal("0.32")))
        await db.commit()
        uid = u.id

        c = await billing_report.user_consumption(db, uid)

    assert c["tokens_in"] == 10
    assert c["tokens_out"] == 5
    assert c["runs"] == 1
    assert c["einkauf_usd"] == Decimal("0.32")
    assert c["verkauf_usd"] == Decimal("0.40")
    assert c["gewinn_usd"] == Decimal("0.08")
    assert c["topups_usd"] == Decimal("5")
    assert c["saldo_usd"] == Decimal("4.60")  # 5 - 0.40


@pytest.mark.asyncio
async def test_search_users_ilike():
    async with SessionLocal() as db:
        marker = uuid4().hex[:8]
        u = User(email=f"sieglinde-{marker}@x.de", google_sub=str(uuid4()),
                 name=f"Sieglinde {marker}")
        db.add(u)
        await db.flush()
        db.add(WalletLedger(user_id=u.id, kind="charge", amount_usd=Decimal("-1.0"),
                            model="m", provider_cost_usd=Decimal("0.8")))
        db.add(WalletLedger(user_id=u.id, kind="topup", amount_usd=Decimal("3")))
        await db.commit()

        # Treffer per email-Fragment
        res = await billing_report.search_users(db, marker)
        assert any(r["email"].startswith(f"sieglinde-{marker}") for r in res)
        hit = next(r for r in res if r["email"].startswith(f"sieglinde-{marker}"))
        assert hit["verkauf_usd"] == Decimal("1.0")
        assert hit["saldo_usd"] == Decimal("2.0")  # 3 - 1.0

        # leere Query → leer
        assert await billing_report.search_users(db, "") == []
