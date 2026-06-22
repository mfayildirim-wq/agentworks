from __future__ import annotations
import pytest
from app.services import image_gen


@pytest.mark.asyncio
async def test_generate_no_key_returns_none(monkeypatch):
    monkeypatch.setattr(image_gen.settings, "openai_api_key", "")
    assert await image_gen.generate("ein hund") is None


@pytest.mark.asyncio
async def test_generate_saves_and_returns_url(monkeypatch, tmp_path):
    import base64
    monkeypatch.setattr(image_gen.settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(image_gen.settings, "media_root", str(tmp_path))
    png = base64.b64encode(b"\x89PNG\r\n\x1a\nFAKE").decode()

    class _Img:
        def __init__(self): self.b64_json = png
    class _Resp:
        data = [_Img()]
    class _Images:
        async def generate(self, **k): return _Resp()
    class _Client:
        images = _Images()
    monkeypatch.setattr("openai.AsyncOpenAI", lambda *a, **k: _Client())

    url = await image_gen.generate("ein hund")
    assert url is not None and url.startswith("/media/generated/") and url.endswith(".png")
    fname = url.split("/")[-1]
    assert (tmp_path / "generated" / fname).exists()


@pytest.mark.asyncio
async def test_generate_failure_returns_none(monkeypatch):
    monkeypatch.setattr(image_gen.settings, "openai_api_key", "sk-test")
    class _Client:
        class images:
            @staticmethod
            async def generate(**k): raise RuntimeError("boom")
    monkeypatch.setattr("openai.AsyncOpenAI", lambda *a, **k: _Client())
    assert await image_gen.generate("x") is None


@pytest.mark.asyncio
async def test_charge_for_image(client):
    from uuid import uuid4
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.db.models import User, Agent, Artifact, Visibility, TemplateOutput
    from app.services import billing
    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        ag = Agent(owner_id=u.id, name="A", role="r"); db.add(ag); await db.flush()
        art = Artifact(owner_id=u.id, agent_id=ag.id, title=f"img-{uuid4()}",
                       output_type=TemplateOutput("html"), visibility=Visibility.PRIVATE)
        db.add(art); await db.flush()
        before = u.balance_usd or 0
        led = await billing.charge_for_image(db, artifact_id=art.id, owner_id=u.id)
        await db.commit()
        assert led is not None and led.kind == "charge" and led.model == "gpt-image-1"
        assert float(led.amount_usd) == -0.02
        u2 = await db.get(User, u.id)
        assert float(u2.balance_usd) == float(before) - 0.02


@pytest.mark.asyncio
async def test_generate_image_tool_balance_guard(client, monkeypatch):
    from decimal import Decimal
    from uuid import uuid4
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.db.models import User
    from app.services import agent_tools, image_gen, billing
    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        u.balance_usd = Decimal("0"); await db.commit(); oid = u.id
    called = {"gen": 0, "charge": 0}
    async def fake_gen(p): called["gen"] += 1; return "/media/generated/x.png"
    async def fake_charge(db, **k): called["charge"] += 1
    monkeypatch.setattr(image_gen, "generate", fake_gen)
    monkeypatch.setattr(billing, "charge_for_image", fake_charge)
    tool = agent_tools.image_tools(artifact_id=uuid4(), owner_id=oid)[0]
    out = await tool("ein hund")
    assert "💳" in out and called["gen"] == 0 and called["charge"] == 0


@pytest.mark.asyncio
async def test_generate_image_tool_success(client, monkeypatch):
    from decimal import Decimal
    from uuid import uuid4
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.db.models import User, Agent, Artifact, Visibility, TemplateOutput
    from app.services import agent_tools, image_gen, billing
    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        u.balance_usd = Decimal("5")
        ag = Agent(owner_id=u.id, name="A", role="r"); db.add(ag); await db.flush()
        art = Artifact(owner_id=u.id, agent_id=ag.id, title=f"img-{uuid4()}",
                       output_type=TemplateOutput("html"), visibility=Visibility.PRIVATE)
        db.add(art); await db.flush(); await db.commit(); oid = u.id; aid = art.id
    calls = {"charge": 0}
    async def fake_gen(p): return "/media/generated/abc.png"
    async def fake_charge(db, *, artifact_id, owner_id): calls["charge"] += 1
    monkeypatch.setattr(image_gen, "generate", fake_gen)
    monkeypatch.setattr(billing, "charge_for_image", fake_charge)
    tool = agent_tools.image_tools(artifact_id=aid, owner_id=oid)[0]
    out = await tool("ein hund im park")
    assert "/media/generated/abc.png" in out and "<img" in out and calls["charge"] == 1
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        u.balance_usd = Decimal("0"); await db.commit()


@pytest.mark.asyncio
async def test_generate_image_tool_gen_failure_no_charge(client, monkeypatch):
    from decimal import Decimal
    from uuid import uuid4
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.db.models import User
    from app.services import agent_tools, image_gen, billing
    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        u.balance_usd = Decimal("5"); await db.commit(); oid = u.id
    calls = {"charge": 0}
    async def fake_gen(p): return None
    async def fake_charge(db, **k): calls["charge"] += 1
    monkeypatch.setattr(image_gen, "generate", fake_gen)
    monkeypatch.setattr(billing, "charge_for_image", fake_charge)
    tool = agent_tools.image_tools(artifact_id=uuid4(), owner_id=oid)[0]
    out = await tool("x")
    assert "konnte nicht erzeugt" in out.lower() and calls["charge"] == 0
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        u.balance_usd = Decimal("0"); await db.commit()


@pytest.mark.asyncio
async def test_image_tools_exposes_generate_image():
    from uuid import uuid4
    from app.services import agent_tools
    tools = agent_tools.image_tools(artifact_id=uuid4(), owner_id=uuid4())
    assert any(getattr(t, "__name__", "") == "generate_image" for t in tools)
