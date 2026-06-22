from __future__ import annotations
import pytest
from uuid import uuid4
from sqlalchemy import select
from app.db.session import SessionLocal
from app.db.models import User, Agent, Artifact, Visibility, TemplateOutput
from app.services import chains


async def _art(db, owner_id, title="X"):
    ag = Agent(owner_id=owner_id, name="A", role="r"); db.add(ag); await db.flush()
    art = Artifact(owner_id=owner_id, agent_id=ag.id, title=title,
                   output_type=TemplateOutput("html"), visibility=Visibility.PRIVATE)
    db.add(art); await db.flush()
    return art


@pytest.mark.asyncio
async def test_set_chain_and_cycle_guard(client):
    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        a = await _art(db, u.id, "A"); b = await _art(db, u.id, "B"); await db.commit()
        ok, why = await chains.set_chain(db, a.id, u.id, next_id=b.id, auto=True)
        assert ok is True
        assert (await db.get(Artifact, a.id)).next_artifact_id == b.id
        assert (await db.get(Artifact, a.id)).chain_auto is True
        ok, why = await chains.set_chain(db, a.id, u.id, next_id=a.id, auto=False)
        assert ok is False and why == "self"
        ok, why = await chains.set_chain(db, b.id, u.id, next_id=a.id, auto=False)
        assert ok is False and why == "cycle"
        ok, why = await chains.set_chain(db, a.id, u.id, next_id=None, auto=False)
        assert ok is True and (await db.get(Artifact, a.id)).next_artifact_id is None


@pytest.mark.asyncio
async def test_set_chain_foreign_owner(client):
    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        other = User(email=f"o-{uuid4()}@x.de", google_sub=str(uuid4()), name="O")
        db.add(other); await db.flush()
        mine = await _art(db, u.id, "mine"); theirs = await _art(db, other.id, "theirs")
        await db.commit()
        ok, why = await chains.set_chain(db, mine.id, u.id, next_id=theirs.id, auto=False)
        assert ok is False and why == "foreign"


@pytest.mark.asyncio
async def test_chain_path_ordered(client):
    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        a = await _art(db, u.id, "A"); b = await _art(db, u.id, "B"); c = await _art(db, u.id, "C")
        await db.commit()
        await chains.set_chain(db, a.id, u.id, next_id=b.id, auto=False)
        await chains.set_chain(db, b.id, u.id, next_id=c.id, auto=False)
        path = await chains.chain_path(db, b.id)
        assert [p["title"] for p in path] == ["A", "B", "C"]
        assert [p["is_self"] for p in path] == [False, True, False]


@pytest.mark.asyncio
async def test_forward_short_output_direct(client, monkeypatch):
    await client.get("/artifacts")
    from app.services import artifacts as artifacts_svc, chat_summary
    calls = {"adjust": None, "summarize": 0}
    async def fake_adjust(db, aid, oid, instruction, **kw):
        calls["adjust"] = (aid, instruction); return uuid4()
    async def fake_summarize(title, content): calls["summarize"] += 1; return "SUM"
    monkeypatch.setattr(artifacts_svc, "adjust", fake_adjust)
    monkeypatch.setattr(chat_summary, "summarize_output", fake_summarize)
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        a = await _art(db, u.id, "A"); b = await _art(db, u.id, "B"); await db.commit()
        await chains.set_chain(db, a.id, u.id, next_id=b.id, auto=False)
        await artifacts_svc.record_version(db, artifact_id=a.id, content="kurzer text",
                                           prompt="p", run_id=None)
        await db.commit()
        rid = await chains.forward(db, a.id)
        assert rid is not None
        assert calls["adjust"][0] == b.id
        assert "kurzer text" in calls["adjust"][1]
        assert calls["summarize"] == 0


@pytest.mark.asyncio
async def test_forward_long_output_summarized(client, monkeypatch):
    await client.get("/artifacts")
    from app.services import artifacts as artifacts_svc, chat_summary
    captured = {}
    async def fake_adjust(db, aid, oid, instruction, **kw):
        captured["instr"] = instruction; return uuid4()
    async def fake_summarize(title, content): return "ZUSAMMENFASSUNG-X"
    monkeypatch.setattr(artifacts_svc, "adjust", fake_adjust)
    monkeypatch.setattr(chat_summary, "summarize_output", fake_summarize)
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        a = await _art(db, u.id, "A"); b = await _art(db, u.id, "B"); await db.commit()
        await chains.set_chain(db, a.id, u.id, next_id=b.id, auto=False)
        await artifacts_svc.record_version(db, artifact_id=a.id, content="x" * 5000,
                                           prompt="p", run_id=None)
        await db.commit()
        await chains.forward(db, a.id)
        assert "ZUSAMMENFASSUNG-X" in captured["instr"]


@pytest.mark.asyncio
async def test_forward_no_next_returns_none(client):
    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        a = await _art(db, u.id, "A"); await db.commit()
        assert await chains.forward(db, a.id) is None


@pytest.mark.asyncio
async def test_get_view_exposes_chain(client):
    await client.get("/artifacts")
    from app.services import artifacts as artifacts_svc
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        a = await _art(db, u.id, "A"); b = await _art(db, u.id, "B"); await db.commit()
        await chains.set_chain(db, a.id, u.id, next_id=b.id, auto=True)
        view = await artifacts_svc.get_view(db, a.id, u)
        assert view.chain_next_id == b.id and view.chain_auto is True
        assert [n.title for n in view.chain_path] == ["A", "B"]


@pytest.mark.asyncio
async def test_auto_hook_fires_only_when_chain_auto(client, monkeypatch):
    await client.get("/artifacts")
    from app.services import chains as chains_mod
    fired = {"n": 0}
    async def fake_forward(db, sid): fired["n"] += 1; return uuid4()
    monkeypatch.setattr(chains_mod, "forward", fake_forward)
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        a = await _art(db, u.id, "A"); b = await _art(db, u.id, "B"); await db.commit()
        await chains_mod.set_chain(db, a.id, u.id, next_id=b.id, auto=False)
        src = await db.get(Artifact, a.id)
        if src.chain_auto and src.next_artifact_id is not None:
            await chains_mod.forward(db, src.id)
        assert fired["n"] == 0
        await chains_mod.set_chain(db, a.id, u.id, next_id=b.id, auto=True)
        src = await db.get(Artifact, a.id)
        if src.chain_auto and src.next_artifact_id is not None:
            await chains_mod.forward(db, src.id)
        assert fired["n"] == 1


@pytest.mark.asyncio
async def test_cycle_guard_long_chain(client):
    # Kette länger als das alte Hop-Limit (25 Knoten) → Rücklink muss trotzdem als Zyklus erkannt werden.
    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        arts = [await _art(db, u.id, f"N{i}") for i in range(25)]
        await db.commit()
        for i in range(24):
            ok, _ = await chains.set_chain(db, arts[i].id, u.id, next_id=arts[i + 1].id, auto=False)
            assert ok is True
        # letzter → erster würde einen 25-Knoten-Zyklus schließen
        ok, why = await chains.set_chain(db, arts[24].id, u.id, next_id=arts[0].id, auto=False)
        assert ok is False and why == "cycle"
