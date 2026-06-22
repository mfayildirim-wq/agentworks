from __future__ import annotations
import pytest
from uuid import uuid4
from sqlalchemy import select
from app.db.session import SessionLocal
from app.db.models import User, Agent, Artifact, Visibility, TemplateOutput


async def _art(db, owner_id, title="X"):
    ag = Agent(owner_id=owner_id, name="A", role="r"); db.add(ag); await db.flush()
    art = Artifact(owner_id=owner_id, agent_id=ag.id, title=title,
                   output_type=TemplateOutput("html"), visibility=Visibility.PRIVATE)
    db.add(art); await db.flush(); return art


@pytest.mark.asyncio
async def test_put_chain_and_forward(client, monkeypatch):
    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        a = await _art(db, u.id, "A"); b = await _art(db, u.id, "B"); await db.commit()
        aid, bid = str(a.id), str(b.id)
    r = await client.put(f"/artifacts/{aid}/chain", json={"next_artifact_id": bid, "auto": True})
    assert r.status_code == 200 and r.json()["ok"] is True
    from app.services import chains
    async def fake_forward(db, sid): return uuid4()
    monkeypatch.setattr(chains, "forward", fake_forward)
    r = await client.post(f"/artifacts/{aid}/forward")
    assert r.status_code == 200 and r.json()["run_id"]


@pytest.mark.asyncio
async def test_put_chain_cycle_400(client):
    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        a = await _art(db, u.id, "A"); b = await _art(db, u.id, "B"); await db.commit()
        aid, bid = str(a.id), str(b.id)
    await client.put(f"/artifacts/{aid}/chain", json={"next_artifact_id": bid, "auto": False})
    r = await client.put(f"/artifacts/{bid}/chain", json={"next_artifact_id": aid, "auto": False})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_forward_without_next_400(client):
    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        a = await _art(db, u.id, "A"); await db.commit(); aid = str(a.id)
    r = await client.post(f"/artifacts/{aid}/forward")
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_chain_foreign_owner_forbidden(client):
    await client.get("/artifacts")
    async with SessionLocal() as db:
        other = User(email=f"o-{uuid4()}@x.de", google_sub=str(uuid4()), name="O")
        db.add(other); await db.flush()
        theirs = await _art(db, other.id, "theirs"); await db.commit(); tid = str(theirs.id)
    r = await client.put(f"/artifacts/{tid}/chain", json={"next_artifact_id": None, "auto": False})
    assert r.status_code == 403
