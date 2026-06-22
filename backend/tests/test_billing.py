from __future__ import annotations

from decimal import Decimal

import pytest

from app.db.session import SessionLocal
from app.services import model_pricing


async def _seed(db):
    await model_pricing.ensure_seed(db)
    await db.commit()


async def test_price_for_known_model():
    async with SessionLocal() as db:
        await _seed(db)
        pin, pout = await model_pricing.price_for(db, "claude-haiku-4-5")
        assert pin == Decimal("1.0")
        assert pout == Decimal("5.0")


async def test_price_for_unknown_model_is_zero():
    async with SessionLocal() as db:
        await _seed(db)
        assert await model_pricing.price_for(db, "gibt-es-nicht") == (Decimal("0"), Decimal("0"))


from sqlalchemy import select

from app.db.models import (
    Agent,
    Artifact,
    ArtifactVersion,
    RunStatus,
    TemplateOutput,
    User,
    Visibility,
    WalletLedger,
    Work,
    WorkRun,
)
from app.services import billing


def test_provider_cost_pure():
    # 1M in @1.0 + 1M out @5.0 = 6.0
    assert billing.provider_cost(Decimal("1.0"), Decimal("5.0"), 1_000_000, 1_000_000) == Decimal("6.0")


async def _user(db) -> User:
    import uuid as _uuid
    sfx = _uuid.uuid4().hex[:8]
    u = User(google_sub=f"bill-{sfx}", email=f"bill-{sfx}@local", name="Bill")
    db.add(u); await db.commit(); await db.refresh(u)
    return u


async def test_top_up_increases_balance():
    async with SessionLocal() as db:
        u = await _user(db)
        await billing.top_up(db, u, Decimal("10"))
        await db.commit()
        await db.refresh(u)
        assert u.balance_usd == Decimal("10")
        rows = (await db.execute(
            select(WalletLedger).where(WalletLedger.user_id == u.id)
        )).scalars().all()
        assert len(rows) == 1 and rows[0].kind == "topup"


async def test_remaining_run_budget():
    async with SessionLocal() as db:
        u = await _user(db)
        u.balance_usd = Decimal("13"); await db.commit()
        assert await billing.remaining_run_budget(db, u) == Decimal("10")  # 13 / 1.30
        u.balance_usd = Decimal("0"); await db.commit()
        assert await billing.remaining_run_budget(db, u) == Decimal("0")


async def _completed_run(db, work_id) -> WorkRun:
    r = WorkRun(work_id=work_id, status=RunStatus.COMPLETED, total_tokens_in=1_000_000,
                total_tokens_out=1_000_000)
    db.add(r); await db.commit(); await db.refresh(r)
    return r


async def _instance(db, owner) -> tuple[Work, Artifact]:
    """Agent + Work (für WorkRun-FK) + Artefakt-Instanz."""
    a = Agent(owner_id=owner.id, name="A", description="", role="assistant", domain="general",
              visibility=Visibility.PRIVATE, price_per_run=0.0)
    db.add(a); await db.commit(); await db.refresh(a)
    w = Work(owner_id=owner.id, title="t", goal="g"); db.add(w)
    art = Artifact(owner_id=owner.id, agent_id=a.id, title="Inst",
                   output_type=TemplateOutput.HTML, visibility=Visibility.UNLISTED)
    db.add(art); await db.commit(); await db.refresh(w); await db.refresh(art)
    return w, art


async def _record_version(db, artifact_id, run_id) -> None:
    n = (await db.execute(
        select(ArtifactVersion).where(ArtifactVersion.artifact_id == artifact_id)
    )).scalars().all()
    db.add(ArtifactVersion(artifact_id=artifact_id, version_no=len(n) + 1,
                           content="<html></html>", prompt="g", run_id=run_id))
    await db.commit()


async def test_first_run_is_free_second_is_charged():
    async with SessionLocal() as db:
        await _seed(db)
        u = await _user(db); u.balance_usd = Decimal("100"); await db.commit()
        w, art = await _instance(db, u)

        # 1. Loop: noch keine Version -> gratis. Danach Version festschreiben (wie der Worker).
        first = await _completed_run(db, w.id)
        led = await billing.charge_for_run(db, first, artifact_id=art.id, owner_id=u.id,
                                           model="claude-haiku-4-5")
        await db.commit()
        assert led is None  # erster Loop gratis
        await db.refresh(u); assert u.balance_usd == Decimal("100")
        await _record_version(db, art.id, first.id)

        # 2. Loop: eine Version existiert -> abgerechnet.
        second = await _completed_run(db, w.id)
        led2 = await billing.charge_for_run(db, second, artifact_id=art.id, owner_id=u.id,
                                            model="claude-haiku-4-5")
        await db.commit()
        # cost*Marge = 6.0 * 1.30 = 7.8
        assert led2 is not None and led2.kind == "charge"
        await db.refresh(u); assert u.balance_usd == Decimal("92.2")


async def test_non_instance_run_is_not_charged():
    async with SessionLocal() as db:
        await _seed(db)
        u = await _user(db); u.balance_usd = Decimal("100"); await db.commit()
        w, _art = await _instance(db, u)
        run = await _completed_run(db, w.id)
        led = await billing.charge_for_run(db, run, artifact_id=None, owner_id=u.id,
                                           model="claude-haiku-4-5")
        await db.commit()
        assert led is None  # ohne Instanz kein Charge
        await db.refresh(u); assert u.balance_usd == Decimal("100")


async def test_charge_idempotent_on_run_id():
    async with SessionLocal() as db:
        await _seed(db)
        u = await _user(db); u.balance_usd = Decimal("100"); await db.commit()
        w, art = await _instance(db, u)
        # Gratis-Lauf bereits verbraucht: eine Version existiert schon.
        await _record_version(db, art.id, None)
        r2 = await _completed_run(db, w.id)
        await billing.charge_for_run(db, r2, artifact_id=art.id, owner_id=u.id, model="claude-haiku-4-5")
        await db.commit()
        again = await billing.charge_for_run(db, r2, artifact_id=art.id, owner_id=u.id, model="claude-haiku-4-5")
        await db.commit()
        assert again is None  # kein Doppel-Charge
        await db.refresh(u); assert u.balance_usd == Decimal("92.2")


from uuid import uuid4

from app.db.models import ModelPrice


@pytest.mark.asyncio
async def test_charge_for_chat_turn_deducts_no_free_run():
    async with SessionLocal() as db:
        model = f"test-model-{uuid4()}"
        db.add(ModelPrice(provider="anthropic", model=model, label="t",
                          input_per_million_usd=Decimal("3"),
                          output_per_million_usd=Decimal("15")))
        u = User(email=f"cb-{uuid4()}@x.de", google_sub=str(uuid4()), balance_usd=Decimal("5"))
        db.add(u); await db.flush()
        aid = uuid4()
        led = await billing.charge_for_chat_turn(
            db, artifact_id=aid, owner_id=u.id, model=model,
            tokens_in=1_000_000, tokens_out=1_000_000)
        await db.commit()
        # cost = 3 + 15 = 18 ; amount = 18 * 1.30 = 23.4 ; KEIN Gratis-Lauf
        assert led is not None
        assert u.balance_usd == Decimal("5") - Decimal("23.4")
        rows = (await db.execute(select(WalletLedger).where(
            WalletLedger.user_id == u.id, WalletLedger.kind == "charge"))).scalars().all()
        assert len(rows) == 1
        assert rows[0].artifact_id == aid and rows[0].tokens_in == 1_000_000


@pytest.mark.asyncio
async def test_charge_for_chat_turn_zero_tokens_no_charge():
    async with SessionLocal() as db:
        u = User(email=f"cb-{uuid4()}@x.de", google_sub=str(uuid4()), balance_usd=Decimal("5"))
        db.add(u); await db.flush()
        led = await billing.charge_for_chat_turn(
            db, artifact_id=uuid4(), owner_id=u.id, model="whatever",
            tokens_in=0, tokens_out=0)
        assert led is None
        assert u.balance_usd == Decimal("5")
