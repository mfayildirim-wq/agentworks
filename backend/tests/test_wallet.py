from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_wallet_by_instance_aggregates(client):
    from uuid import UUID, uuid4
    from decimal import Decimal
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.db.models import User, WalletLedger, Artifact, Agent, Visibility, TemplateOutput

    await client.get("/artifacts")  # stellt sicher: User existiert
    async with SessionLocal() as db:
        # genau den authentifizierten Test-Nutzer wählen (nicht .first() — die DB ist
        # geteilt; .first() ist ohne ORDER BY nicht deterministisch der Auth-Nutzer).
        u = (await db.execute(
            select(User).where(User.google_sub == "test-user")
        )).scalars().first()
        ag = Agent(owner_id=u.id, name="A", role="r"); db.add(ag); await db.flush()
        art = Artifact(owner_id=u.id, agent_id=ag.id, title=f"Inst-{uuid4()}",
                       output_type=TemplateOutput("html"), visibility=Visibility.UNLISTED)
        db.add(art); await db.flush()
        db.add(WalletLedger(user_id=u.id, kind="charge", amount_usd=Decimal("-0.20"),
                            artifact_id=art.id, model="m", description="Chat-Lauf m"))
        db.add(WalletLedger(user_id=u.id, kind="charge", amount_usd=Decimal("-0.05"),
                            artifact_id=art.id, model="m", description="Chat-Lauf m"))
        db.add(WalletLedger(user_id=u.id, kind="topup", amount_usd=Decimal("10"),
                            description="topup"))   # darf NICHT in by-instance auftauchen
        await db.commit()
        art_id = str(art.id)

    r = await client.get("/wallet/by-instance")
    assert r.status_code == 200
    data = r.json()
    row = next((x for x in data if x["artifact_id"] == art_id), None)
    assert row is not None
    assert abs(float(row["total_usd"]) - 0.25) < 1e-9
    assert row["runs"] == 2
    assert row["title"].startswith("Inst-")


@pytest.mark.asyncio
async def test_wallet_ledger_includes_app_name(client):
    from uuid import uuid4
    from decimal import Decimal
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.db.models import User, WalletLedger, Artifact, Agent, Visibility, TemplateOutput

    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = (await db.execute(
            select(User).where(User.google_sub == "test-user"))).scalars().first()
        ag = Agent(owner_id=u.id, name="A", role="r"); db.add(ag); await db.flush()
        art = Artifact(owner_id=u.id, agent_id=ag.id, title=f"MeineApp-{uuid4()}",
                       output_type=TemplateOutput("html"), visibility=Visibility.UNLISTED)
        db.add(art); await db.flush()
        db.add(WalletLedger(user_id=u.id, kind="charge", amount_usd=Decimal("-0.10"),
                            artifact_id=art.id, model="m", description="Chat-Lauf m"))
        db.add(WalletLedger(user_id=u.id, kind="topup", amount_usd=Decimal("5"),
                            description="topup"))
        await db.commit()
        title = art.title

    r = await client.get("/wallet")
    assert r.status_code == 200
    ledger = r.json()["ledger"]
    charge = next((x for x in ledger if x.get("app_name") == title), None)
    assert charge is not None
    topup = next((x for x in ledger if x["kind"] == "topup"), None)
    assert topup is not None and topup["app_name"] is None
