from __future__ import annotations
from decimal import Decimal

import pytest


@pytest.mark.asyncio
async def test_creator_royalty_credits_template_owner(client):
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.db.models import User, Agent, Template, Artifact, Visibility, TemplateOutput, WalletLedger
    from app.services import billing

    await client.get("/artifacts")
    async with SessionLocal() as db:
        user = (await db.execute(select(User).where(User.google_sub == "test-user"))).scalars().first()
        # Ersteller (anderer Nutzer als der Instanz-Nutzer).
        creator = User(google_sub="creator-x", email="creator-x@local", name="Creator X",
                       balance_usd=Decimal("0"))
        db.add(creator); await db.flush()
        ag = Agent(owner_id=creator.id, name="A", role="r"); db.add(ag); await db.flush()
        tpl = Template(owner_id=creator.id, title="Travel", output_type=TemplateOutput.HTML,
                       visibility=Visibility.PUBLIC, config={"agent_ids": [str(ag.id)]})
        db.add(tpl); await db.flush()
        art = Artifact(owner_id=user.id, agent_id=ag.id, template_id=tpl.id, title="X",
                       output_type=TemplateOutput.HTML, visibility=Visibility.PRIVATE)
        db.add(art); await db.flush()

        led = await billing._credit_creator_royalty(
            db, artifact_id=art.id, owner_id=user.id, cost=Decimal("1.00"), model="claude-haiku-4-5")
        await db.commit()
        assert led is not None and led.kind == "royalty"
        # 5 % von 1.00 = 0.05
        assert led.amount_usd == Decimal("0.050000")
        await db.refresh(creator)
        assert creator.balance_usd == Decimal("0.050000")


@pytest.mark.asyncio
async def test_no_royalty_on_own_template(client):
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.db.models import User, Agent, Template, Artifact, Visibility, TemplateOutput
    from app.services import billing

    await client.get("/artifacts")
    async with SessionLocal() as db:
        user = (await db.execute(select(User).where(User.google_sub == "test-user"))).scalars().first()
        ag = Agent(owner_id=user.id, name="B", role="r"); db.add(ag); await db.flush()
        tpl = Template(owner_id=user.id, title="Eigen", output_type=TemplateOutput.HTML,
                       visibility=Visibility.PRIVATE, config={"agent_ids": [str(ag.id)]})
        db.add(tpl); await db.flush()
        art = Artifact(owner_id=user.id, agent_id=ag.id, template_id=tpl.id, title="Y",
                       output_type=TemplateOutput.HTML, visibility=Visibility.PRIVATE)
        db.add(art); await db.flush()
        led = await billing._credit_creator_royalty(
            db, artifact_id=art.id, owner_id=user.id, cost=Decimal("1.00"), model="m")
        assert led is None   # eigene Vorlage → keine Gutschrift


def test_margin_is_thirty_percent():
    from app.services import billing
    assert billing.MARGIN == Decimal("1.30")
    assert billing.CREATOR_SHARE == Decimal("0.05")
