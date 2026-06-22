import pytest
from uuid import uuid4
from app.services import google_oauth as go

def test_state_roundtrip():
    uid, aid = uuid4(), uuid4()
    s = go.encode_state(uid, aid)
    out = go.decode_state(s)
    assert out is not None and out["user_id"] == str(uid) and out["artifact_id"] == str(aid)

def test_state_tampered_or_expired_returns_none():
    assert go.decode_state("garbage") is None
    s = go.encode_state(uuid4(), uuid4(), ttl_seconds=-1)   # schon abgelaufen
    assert go.decode_state(s) is None

def test_build_auth_url_contains_scope_and_offline(monkeypatch):
    monkeypatch.setattr(go.settings, "google_client_id", "cid")
    url = go.build_auth_url("STATE")
    assert "accounts.google.com" in url and "calendar.events" in url
    assert "access_type=offline" in url and "state=STATE" in url


def test_scopes_for_kinds():
    assert "calendar.events" in go.scopes_for("google_calendar")
    # gmail-Registry-Eintrag kommt in GM2; hier nur calendar prüfen, plus unbekannt → "":
    assert go.scopes_for("unbekannt") == ""

def test_state_carries_kind():
    from uuid import uuid4
    s = go.encode_state(uuid4(), uuid4(), "gmail")
    out = go.decode_state(s)
    assert out is not None and out["kind"] == "gmail"

def test_state_default_kind_calendar():
    from uuid import uuid4
    out = go.decode_state(go.encode_state(uuid4(), uuid4()))
    assert out["kind"] == "google_calendar"


@pytest.mark.asyncio
async def test_start_redirects_for_owner(client, monkeypatch):
    monkeypatch.setattr(go.settings, "google_client_id", "cid")
    from uuid import UUID
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.db.models import User
    from app.services import artifacts as art_svc
    await client.get("/artifacts")
    async with SessionLocal() as db:
        owner = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        resp = await client.post("/agents", json={"name": "Cal"})
        agent_id = UUID(resp.json()["id"])
        art = await art_svc.create_instance(db, owner_id=owner.id, agent_id=agent_id,
                                            title="Kal", output_type="html")
        aid = str(art.id)
    r = await client.get(f"/oauth/google/start?artifact_id={aid}", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert "accounts.google.com" in r.headers["location"]


@pytest.mark.asyncio
async def test_callback_stores_connection(client, monkeypatch):
    from uuid import UUID
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.db.models import User
    from app.services import artifacts as art_svc, artifact_connections as conn_svc, google_oauth as go2
    await client.get("/artifacts")
    async with SessionLocal() as db:
        owner = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        resp = await client.post("/agents", json={"name": "Cal2"})
        agent_id = UUID(resp.json()["id"])
        art = await art_svc.create_instance(db, owner_id=owner.id, agent_id=agent_id,
                                            title="Kal2", output_type="html")
        aid, oid = art.id, owner.id
    state = go2.encode_state(oid, aid)
    async def fake_exchange(code): return {"access_token": "AT", "refresh_token": "RT", "expires_in": 3600}
    monkeypatch.setattr(go2, "exchange_code", fake_exchange)
    r = await client.get(f"/oauth/google/callback?code=XYZ&state={state}", follow_redirects=False)
    assert r.status_code in (302, 307)
    async with SessionLocal() as db:
        conn = await conn_svc.get_connection(db, aid, oid, "google_calendar")
        assert conn is not None
        safe = conn_svc.to_safe_out(conn)
        assert "secret" not in safe and "RT" not in str(safe)   # kein Token nach außen


@pytest.mark.asyncio
async def test_calendar_tools_use_token(monkeypatch):
    from app.services import agent_tools, google_oauth as go2
    from uuid import uuid4
    captured = {}
    async def fake_token(db, aid, oid): return "AT123"
    monkeypatch.setattr(go2, "get_valid_access_token", fake_token)
    class _Resp:
        def raise_for_status(self): pass
        def json(self): return {"items": [{"summary": "Termin A", "start": {"dateTime": "2026-06-17T10:00:00Z"}}]}
    class _Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url, headers=None, params=None):
            captured["auth"] = headers.get("Authorization"); return _Resp()
        async def post(self, url, headers=None, json=None):
            captured["auth"] = headers.get("Authorization"); return _Resp()
    monkeypatch.setattr(agent_tools.httpx, "AsyncClient", lambda *a, **k: _Client())
    tools = agent_tools.google_calendar_tools(artifact_id=uuid4(), owner_id=uuid4())
    list_tool = next(t for t in tools if t.__name__ == "calendar_list_events")
    out = await list_tool()
    assert "Termin A" in out and captured["auth"] == "Bearer AT123"


@pytest.mark.asyncio
async def test_gmail_send_builds_raw(monkeypatch):
    from app.services import agent_tools, google_oauth as go2
    from uuid import uuid4
    captured = {}
    async def fake_token(db, aid, oid, kind): assert kind == "gmail"; return "AT"
    monkeypatch.setattr(go2, "get_valid_access_token", fake_token)
    class _Resp:
        def raise_for_status(self): pass
        def json(self): return {"id": "m1"}
    class _Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, headers=None, json=None):
            captured["auth"] = headers.get("Authorization"); captured["raw"] = json.get("raw"); return _Resp()
        async def get(self, url, headers=None, params=None): return _Resp()
    monkeypatch.setattr(agent_tools.httpx, "AsyncClient", lambda *a, **k: _Client())
    tools = agent_tools.gmail_tools(artifact_id=uuid4(), owner_id=uuid4())
    send = next(t for t in tools if t.__name__ == "gmail_send")
    out = await send("a@b.de", "Hallo", "Text")
    assert captured["auth"] == "Bearer AT"
    import base64
    decoded = base64.urlsafe_b64decode(captured["raw"]).decode()
    assert "To: a@b.de" in decoded and "Subject: Hallo" in decoded and "Text" in decoded


@pytest.mark.asyncio
async def test_gmail_send_strips_crlf_header_injection(monkeypatch):
    """CRLF in to/subject darf KEINE zusätzlichen Header (z.B. Bcc) injizieren."""
    from app.services import agent_tools, google_oauth as go2
    from uuid import uuid4
    import base64
    captured = {}
    async def fake_token(db, aid, oid, kind): return "AT"
    monkeypatch.setattr(go2, "get_valid_access_token", fake_token)
    class _Resp:
        def raise_for_status(self): pass
        def json(self): return {"id": "m1"}
    class _Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, headers=None, json=None): captured["raw"] = json.get("raw"); return _Resp()
        async def get(self, url, headers=None, params=None): return _Resp()
    monkeypatch.setattr(agent_tools.httpx, "AsyncClient", lambda *a, **k: _Client())
    tools = agent_tools.gmail_tools(artifact_id=uuid4(), owner_id=uuid4())
    send = next(t for t in tools if t.__name__ == "gmail_send")
    await send("ok@b.de\r\nBcc: evil@x.de", "Hi\r\nBcc: evil2@x.de", "Body")
    decoded = base64.urlsafe_b64decode(captured["raw"]).decode(errors="ignore")
    # Die eingeschleusten Header dürfen NICHT als eigene Header-Zeilen erscheinen.
    assert "\nBcc: evil@x.de" not in decoded
    assert "\nBcc: evil2@x.de" not in decoded
