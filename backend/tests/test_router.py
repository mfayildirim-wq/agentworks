from __future__ import annotations
import pytest
from decimal import Decimal
from sqlalchemy import select
from app.db.session import SessionLocal
from app.db.models import User, WalletLedger
from app.services import billing, model_pricing


@pytest.mark.asyncio
async def test_charge_for_router_turn(client):
    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        await model_pricing.ensure_seed(db)
        await db.commit()
        led = await billing.charge_for_router_turn(
            db, owner_id=u.id, model="claude-haiku-4-5", tokens_in=1000, tokens_out=200)
        await db.commit()
        assert led is not None and led.artifact_id is None and led.kind == "charge"
        assert led.amount_usd < 0
        none = await billing.charge_for_router_turn(
            db, owner_id=u.id, model="claude-haiku-4-5", tokens_in=0, tokens_out=0)
        assert none is None


@pytest.mark.asyncio
async def test_route_single_candidate_no_model(monkeypatch):
    from uuid import uuid4
    from app.services import router_agent
    monkeypatch.setattr("agent_runtime.model_client.make_model_client",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("kein Modell bei 1 Kandidat")))
    aid = uuid4()
    async with SessionLocal() as db:
        d = await router_agent.route(db, uuid4(), message="hi", active=None,
                                     candidates=[{"artifact_id": aid, "title": "A", "description": "x"}])
    assert d.action == "use" and d.artifact_id == aid


@pytest.mark.asyncio
async def test_route_uses_model_decision(client, monkeypatch):
    from uuid import uuid4
    from app.db.models import User
    from app.services import router_agent, model_pricing
    await client.get("/artifacts")
    class _U:
        prompt_tokens = 50; completion_tokens = 10
    class _Res:
        content = '{"action":"use","n":2}'
    class _Client:
        async def create(self, *a, **k): return _Res()
        def total_usage(self): return _U()
        async def close(self): pass
    monkeypatch.setattr("agent_runtime.model_client.make_model_client", lambda *a, **k: _Client())
    a1, a2 = uuid4(), uuid4()
    async with SessionLocal() as db:
        await model_pricing.ensure_seed(db); await db.commit()
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        d = await router_agent.route(db, u.id, message="termine", active=None, candidates=[
            {"artifact_id": a1, "title": "Travel", "description": "Reisen"},
            {"artifact_id": a2, "title": "Kalender", "description": "Termine"}])
        await db.commit()
    assert d.action == "use" and d.artifact_id == a2


@pytest.mark.asyncio
async def test_route_parse_error_falls_back_to_ask(client, monkeypatch):
    from uuid import uuid4
    from app.db.models import User
    from app.services import router_agent, model_pricing
    await client.get("/artifacts")
    class _U:
        prompt_tokens = 5; completion_tokens = 1
    class _Res:
        content = "kein json"
    class _Client:
        async def create(self, *a, **k): return _Res()
        def total_usage(self): return _U()
        async def close(self): pass
    monkeypatch.setattr("agent_runtime.model_client.make_model_client", lambda *a, **k: _Client())
    async with SessionLocal() as db:
        await model_pricing.ensure_seed(db); await db.commit()
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        d = await router_agent.route(db, u.id, message="?", active=None, candidates=[
            {"artifact_id": uuid4(), "title": "A", "description": "x"},
            {"artifact_id": uuid4(), "title": "B", "description": "y"}])
        await db.commit()
    assert d.action == "ask" and len(d.candidates) == 2


async def _mk_instance(db, owner_id, title="Inst"):
    from app.db.models import Agent, Artifact, Visibility, TemplateOutput
    ag = Agent(owner_id=owner_id, name="A", role="r"); db.add(ag); await db.flush()
    art = Artifact(owner_id=owner_id, agent_id=ag.id, title=title,
                   output_type=TemplateOutput("html"), visibility=Visibility.PRIVATE)
    db.add(art); await db.flush()
    return art


async def _reset_user(db, owner_id):
    """Tests teilen sich den 'test-user'; vor dem Anlegen eigener Instanzen die
    Reste vorheriger Tests entfernen, damit der Kandidaten-Index deterministisch ist."""
    from sqlalchemy import delete
    from app.db.models import Artifact, ChannelSession
    await db.execute(delete(ChannelSession).where(ChannelSession.user_id == owner_id))
    await db.execute(delete(Artifact).where(Artifact.owner_id == owner_id))
    await db.flush()


async def _cleanup_user(db, owner_id):
    """Nach Tests, die Guthaben/Telegram setzen, den geteilten 'test-user' wieder
    neutralisieren, damit nichts in nachfolgende Tests (z. B. Wallet) leckt."""
    from decimal import Decimal
    from sqlalchemy import delete, update
    from app.db.models import Artifact, ChannelSession, User
    await db.execute(delete(ChannelSession).where(ChannelSession.user_id == owner_id))
    await db.execute(delete(Artifact).where(Artifact.owner_id == owner_id))
    await db.execute(update(User).where(User.id == owner_id)
                     .values(balance_usd=Decimal("0"), telegram_chat_id=None))


@pytest.mark.asyncio
async def test_handle_inbound_unlinked_user(client):
    from app.services import channel_dispatch
    async with SessionLocal() as db:
        reply = await channel_dispatch.handle_inbound(db, "telegram", "999999", "hallo")
    assert "verbind" in reply.lower()


@pytest.mark.asyncio
async def test_handle_inbound_single_instance_enqueues_turn(client, monkeypatch):
    # Fix 1: handle_inbound RUNT den Turn nicht selbst, sondern enqueued ihn (→ None).
    from decimal import Decimal
    from app.db.models import User
    from app.services import channel_dispatch
    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        await _reset_user(db, u.id)
        u.telegram_chat_id = "tg-1"; u.balance_usd = Decimal("5")
        art = await _mk_instance(db, u.id, "Solo"); await db.commit(); aid = str(art.id)
    captured = {}
    def fake_enqueue(channel, cuid, artifact_id, owner_id, text):
        captured["artifact_id"] = str(artifact_id); captured["text"] = text
    monkeypatch.setattr(channel_dispatch, "_enqueue_turn", fake_enqueue)
    async with SessionLocal() as db:
        reply = await channel_dispatch.handle_inbound(db, "telegram", "tg-1", "hi")
    assert reply is None                       # Turn läuft asynchron im Worker
    assert captured["artifact_id"] == aid and captured["text"] == "hi"
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        await _cleanup_user(db, u.id); await db.commit()


@pytest.mark.asyncio
async def test_run_instance_turn(client, monkeypatch):
    # Der eigentliche Turn (im Worker) liefert den Antworttext.
    from decimal import Decimal
    from app.db.models import User, ArtifactMessage
    from app.services import channel_dispatch, artifact_chat, artifact_chat_runtime as rt, billing
    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        await _reset_user(db, u.id)
        u.balance_usd = Decimal("5")
        art = await _mk_instance(db, u.id, "Solo"); await db.commit(); aid = art.id; oid = u.id
    async def fake_completer(db, artifact_id):
        class _Meta: model="claude-haiku-4-5"; owner_id=None; tokens_in=1; tokens_out=1
        return (lambda s, m: None), _Meta()
    async def fake_run_turn(db, *, artifact_id, complete, **k):
        m = ArtifactMessage(artifact_id=artifact_id, role="assistant", content="Hallo zurück!")
        db.add(m); await db.flush(); return m
    async def fake_charge(db, **k): return None
    monkeypatch.setattr(rt, "make_completer", fake_completer)
    monkeypatch.setattr(artifact_chat, "run_turn", fake_run_turn)
    monkeypatch.setattr(billing, "charge_for_chat_turn", fake_charge)
    async with SessionLocal() as db:
        reply = await channel_dispatch.run_instance_turn(db, artifact_id=aid, owner_id=oid, text="hi")
    assert reply == "Hallo zurück!"
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        await _cleanup_user(db, u.id); await db.commit()


@pytest.mark.asyncio
async def test_tick_telegram_routes_non_start(monkeypatch):
    from app.services.notify import channels
    import app.cron_runner as cr
    sent = {}
    async def fake_api(method, payload):
        if method == "getUpdates":
            return {"result": [{"update_id": 1, "message": {"text": "hallo agent",
                    "chat": {"id": 555}}}]}
        if method == "sendMessage":
            sent["text"] = payload["text"]; sent["chat"] = payload["chat_id"]
        return {"result": []}
    monkeypatch.setattr(channels, "telegram_configured", lambda: True)
    monkeypatch.setattr(channels, "telegram_api", fake_api)
    from app.services import channel_dispatch
    async def fake_handle(db, channel, cuid, text):
        assert channel == "telegram" and text == "hallo agent"
        return "ANTWORT"
    monkeypatch.setattr(channel_dispatch, "handle_inbound", fake_handle)
    cr._tg_offset = 0
    await cr.tick_telegram()
    assert sent.get("text") == "ANTWORT" and str(sent.get("chat")) == "555"


@pytest.mark.asyncio
async def test_tick_telegram_start_still_links(monkeypatch):
    # /start darf weiterhin den Linking-Pfad nehmen (nicht den Verteiler).
    from app.services.notify import channels
    from app.services import channel_dispatch
    import app.cron_runner as cr
    called = {"dispatch": 0}
    async def fake_api(method, payload):
        if method == "getUpdates":
            return {"result": [{"update_id": 2, "message": {"text": "/start abc",
                    "chat": {"id": 777}}}]}
        return {"result": []}
    async def fake_handle(db, channel, cuid, text):
        called["dispatch"] += 1; return "x"
    monkeypatch.setattr(channels, "telegram_configured", lambda: True)
    monkeypatch.setattr(channels, "telegram_api", fake_api)
    monkeypatch.setattr(channel_dispatch, "handle_inbound", fake_handle)
    cr._tg_offset = 0
    await cr.tick_telegram()
    assert called["dispatch"] == 0   # /start NICHT über den Verteiler


@pytest.mark.asyncio
async def test_handle_inbound_balance_guard(client):
    from decimal import Decimal
    from app.db.models import User
    from app.services import channel_dispatch
    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        u.telegram_chat_id = "tg-broke"; u.balance_usd = Decimal("0")
        await _reset_user(db, u.id)
        await _mk_instance(db, u.id, "X"); await db.commit()
    async with SessionLocal() as db:
        reply = await channel_dispatch.handle_inbound(db, "telegram", "tg-broke", "hi")
    assert "💳" in reply


@pytest.mark.asyncio
async def test_handle_inbound_ask_then_pick(client, monkeypatch):
    from decimal import Decimal
    from app.db.models import User, ArtifactMessage
    from app.services import channel_dispatch, router_agent, artifact_chat, artifact_chat_runtime as rt, billing
    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        u.telegram_chat_id = "tg-2"; u.balance_usd = Decimal("5")
        await _reset_user(db, u.id)
        a1 = await _mk_instance(db, u.id, "Travel"); a2 = await _mk_instance(db, u.id, "Kalender")
        await db.commit()
    expected = {}
    async def fake_route(db, owner_id, *, message, active, candidates):
        # n=2 → 2. Kandidat (Reihenfolge unabhängig vom Erzeugungsdatum festhalten).
        expected["n2"] = str(candidates[1]["artifact_id"])
        return router_agent.RouteDecision(action="ask", candidates=[
            {"n": 1, "artifact_id": candidates[0]["artifact_id"], "title": "A"},
            {"n": 2, "artifact_id": candidates[1]["artifact_id"], "title": "B"}])
    monkeypatch.setattr(router_agent, "route", fake_route)
    async with SessionLocal() as db:
        reply = await channel_dispatch.handle_inbound(db, "telegram", "tg-2", "was geht?")
    assert "1)" in reply and "2)" in reply
    # Folge-Nachricht "2" → 2. Kandidat gewählt → Turn enqueued (None), nicht inline gefahren.
    captured = {}
    def fake_enqueue(channel, cuid, artifact_id, owner_id, text):
        captured["artifact_id"] = str(artifact_id); captured["text"] = text
    monkeypatch.setattr(channel_dispatch, "_enqueue_turn", fake_enqueue)
    async with SessionLocal() as db:
        reply2 = await channel_dispatch.handle_inbound(db, "telegram", "tg-2", "2")
    assert reply2 is None and captured["artifact_id"] == expected["n2"] and captured["text"] == "was geht?"
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        await _cleanup_user(db, u.id); await db.commit()


@pytest.mark.asyncio
async def test_handle_inbound_drops_stale_foreign_session(client, monkeypatch):
    # Chat wurde an ein anderes Konto neu verknüpft: alte Session (fremder Nutzer +
    # fremde pending-Kandidaten) darf NIE übernommen werden.
    from decimal import Decimal
    from uuid import uuid4
    from sqlalchemy import select
    from app.db.models import User, ArtifactMessage, ChannelSession
    from app.services import channel_dispatch, artifact_chat, artifact_chat_runtime as rt, billing
    await client.get("/artifacts")
    async with SessionLocal() as db:
        me = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        await _reset_user(db, me.id)
        me.telegram_chat_id = "tg-shared"; me.balance_usd = Decimal("5")
        mine = await _mk_instance(db, me.id, "Mein")
        other = User(email=f"a-{uuid4()}@x.de", google_sub=str(uuid4()), name="A")
        db.add(other); await db.flush()
        # stale Session: gehört other, zeigt auf fremde Instanz
        db.add(ChannelSession(channel="telegram", channel_user_id="tg-shared",
                              user_id=other.id, active_artifact_id=None,
                              pending={"candidates": [{"n": 1, "artifact_id": str(uuid4()), "title": "Fremd"}], "text": "x"}))
        await db.commit(); mine_id = str(mine.id)
    captured = {}
    def fake_enqueue(channel, cuid, artifact_id, owner_id, text):
        captured["artifact_id"] = str(artifact_id)
    monkeypatch.setattr(channel_dispatch, "_enqueue_turn", fake_enqueue)
    async with SessionLocal() as db:
        reply = await channel_dispatch.handle_inbound(db, "telegram", "tg-shared", "1")
    # NICHT die fremde pending-Auswahl, sondern frisch auf MEINE einzige Instanz geroutet
    assert reply is None and captured["artifact_id"] == mine_id
    async with SessionLocal() as db:
        s = (await db.execute(select(ChannelSession).where(
            ChannelSession.channel_user_id=="tg-shared"))).scalars().first()
        me = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        assert s.user_id == me.id   # Session gehört jetzt mir
        await _cleanup_user(db, me.id); await db.commit()


@pytest.mark.asyncio
async def test_run_instance_turn_empty_reply_falls_back_to_link(client, monkeypatch):
    # Fix 2: Canvas-Agent ohne Chat-Text → Antwort = Hinweis + Link zur Seite.
    from decimal import Decimal
    from app.db.models import User
    from app.services import channel_dispatch, artifact_chat, artifact_chat_runtime as rt, billing
    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        await _reset_user(db, u.id)
        u.balance_usd = Decimal("5")
        art = await _mk_instance(db, u.id, "Canvas"); await db.commit(); aid = art.id; oid = u.id
    async def fake_completer(db, artifact_id):
        class _Meta: model="claude-haiku-4-5"; owner_id=None; tokens_in=1; tokens_out=1
        return (lambda s, m: None), _Meta()
    async def fake_run_turn(db, *, artifact_id, complete, **k):
        return None   # nur Seiten-Update, kein Chat-Text
    monkeypatch.setattr(rt, "make_completer", fake_completer)
    monkeypatch.setattr(artifact_chat, "run_turn", fake_run_turn)
    monkeypatch.setattr(billing, "charge_for_chat_turn", lambda *a, **k: _noop())
    async with SessionLocal() as db:
        reply = await channel_dispatch.run_instance_turn(db, artifact_id=aid, owner_id=oid, text="hi")
    assert "/artifacts/" in reply and str(aid) in reply
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        await _cleanup_user(db, u.id); await db.commit()


@pytest.mark.asyncio
async def test_candidates_capped(client, monkeypatch):
    # Fix 3: Kandidatenliste wird gedeckelt (nicht alle Instanzen).
    from app.db.models import User
    from app.services import channel_dispatch
    await client.get("/artifacts")
    monkeypatch.setattr(channel_dispatch, "_MAX_CANDIDATES", 2)
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        await _reset_user(db, u.id)
        for i in range(3):
            await _mk_instance(db, u.id, f"I{i}")
        await db.commit(); oid = u.id
    async with SessionLocal() as db:
        cands = await channel_dispatch._candidates(db, oid)
    assert len(cands) == 2
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        await _cleanup_user(db, u.id); await db.commit()
