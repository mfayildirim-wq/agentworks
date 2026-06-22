import pytest
from uuid import UUID
from decimal import Decimal
from sqlalchemy import select, func


@pytest.mark.asyncio
async def test_chat_turn_charges_wallet(client, monkeypatch):
    import app.workers as workers
    from app.services import artifact_chat_runtime as rt
    from app.db.session import SessionLocal
    from app.db.models import User, WalletLedger, Artifact

    # Instanz anlegen (Muster wie test_artifacts.py: Agent + Template + instantiate)
    from tests.test_artifacts import _user_and_agent      # vorhandenen Helfer wiederverwenden
    agent_id = await _user_and_agent(client)
    t = await client.post("/templates", json={
        "title": "T", "visibility": "public", "output_type": "html",
        "config": {"agent_ids": [agent_id], "prompt_template": "Plane {{x}}."},
        "input_schema": [{"key": "x", "label": "X", "type": "string", "required": True}]})
    tid = t.json()["id"]
    inst = await client.post(f"/templates/{tid}/instantiate", json={"inputs": {"x": "Rom"}})
    artifact_id = UUID(inst.json()["artifact_id"])

    # Owner mit Guthaben; ModelPrice für das Agent-Modell
    async with SessionLocal() as db:
        art = await db.get(Artifact, artifact_id)
        owner = await db.get(User, art.owner_id)
        owner.balance_usd = Decimal("5")
        await db.commit()

    # make_completer mocken: liefert (complete, meta) mit gesetzten Tokens
    class _Meta:
        def __init__(self): self.model="anthropic-x"; self.owner_id=None; self.tokens_in=1000; self.tokens_out=500
    async def _fake_make_completer(db, aid):
        m = _Meta()
        from app.db.models import Artifact as _A
        a = await db.get(_A, aid); m.owner_id = a.owner_id
        async def _complete(system, message): return "ok"
        return _complete, m
    monkeypatch.setattr(rt, "make_completer", _fake_make_completer)
    # price_for mocken, damit kein ModelPrice-Seed nötig ist
    from app.services import model_pricing
    async def _price(db, model): return (Decimal("3"), Decimal("15"))
    monkeypatch.setattr(model_pricing, "price_for", _price)

    await workers._execute_chat_turn_async(artifact_id)

    async with SessionLocal() as db:
        charges = (await db.execute(select(WalletLedger).where(
            WalletLedger.artifact_id == artifact_id, WalletLedger.kind == "charge"))).scalars().all()
        assert len(charges) == 1
        owner2 = await db.get(User, (await db.get(Artifact, artifact_id)).owner_id)
        assert owner2.balance_usd < Decimal("5")   # Guthaben gesunken


@pytest.mark.asyncio
async def test_chat_turn_blocked_when_no_balance(client, monkeypatch):
    import app.workers as workers
    from app.services import artifact_chat, artifact_chat_runtime as rt
    from app.db.session import SessionLocal
    from app.db.models import User, Artifact, ArtifactMessage
    from sqlalchemy import select

    from tests.test_artifacts import _user_and_agent
    agent_id = await _user_and_agent(client)
    t = await client.post("/templates", json={
        "title": "T", "visibility": "public", "output_type": "html",
        "config": {"agent_ids": [agent_id], "prompt_template": "Plane {{x}}."},
        "input_schema": [{"key": "x", "label": "X", "type": "string", "required": True}]})
    tid = t.json()["id"]
    inst = await client.post(f"/templates/{tid}/instantiate", json={"inputs": {"x": "Rom"}})
    artifact_id = UUID(inst.json()["artifact_id"])
    async with SessionLocal() as db:
        art = await db.get(Artifact, artifact_id)
        owner = await db.get(User, art.owner_id)
        owner.balance_usd = Decimal("0")
        await db.commit()

    called = {"v": False}
    async def _boom_run_turn(*a, **k): called["v"] = True
    monkeypatch.setattr(artifact_chat, "run_turn", _boom_run_turn)

    await workers._execute_chat_turn_async(artifact_id)

    assert called["v"] is False    # kein LLM-Lauf bei leerem Guthaben
    async with SessionLocal() as db:
        msgs = (await db.execute(select(ArtifactMessage).where(
            ArtifactMessage.artifact_id == artifact_id,
            ArtifactMessage.role == "assistant"))).scalars().all()
        assert any("Guthaben" in (m.content or "") for m in msgs)
