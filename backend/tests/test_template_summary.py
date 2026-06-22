from __future__ import annotations
import pytest
from app.services import template_summary


async def _async(v):
    return v


@pytest.mark.asyncio
async def test_summarize_prompt_empty_returns_empty():
    assert await template_summary.summarize_prompt("") == ""
    assert await template_summary.summarize_prompt("   ") == ""


@pytest.mark.asyncio
async def test_summarize_prompt_uses_model(monkeypatch):
    class _Res:
        content = "Plant Reisen und erstellt Reisepläne."
    class _Client:
        async def create(self, *a, **k): return _Res()
        async def close(self): pass
    monkeypatch.setattr("agent_runtime.model_client.make_model_client", lambda spec, ctx: _Client())
    out = await template_summary.summarize_prompt("Du bist ein Reiseplaner-Agent ...")
    assert out == "Plant Reisen und erstellt Reisepläne."


@pytest.mark.asyncio
async def test_summarize_prompt_failclosed(monkeypatch):
    class _Client:
        async def create(self, *a, **k): raise RuntimeError("boom")
        async def close(self): pass
    monkeypatch.setattr("agent_runtime.model_client.make_model_client", lambda spec, ctx: _Client())
    assert await template_summary.summarize_prompt("irgendein prompt") == ""


@pytest.mark.asyncio
async def test_create_template_description_from_prompt(client, monkeypatch):
    from uuid import uuid4
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.db.models import User, Template
    from app.schemas.templates import AgentTemplateCreate
    from app.services import templates as tpl_svc, template_summary
    monkeypatch.setattr(template_summary, "summarize_prompt",
                        lambda prompt: _async("AUTO: Reise-Agent"))
    await client.get("/artifacts")
    async with SessionLocal() as db:
        me = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        out = await tpl_svc.create_agent_template(db, me, AgentTemplateCreate(
            category="Everyday", name=f"T-{uuid4()}", prompt="Du bist ein Reiseplaner.",
            model="claude-haiku-4-5", html_template_id="classic",
            description="vom-nutzer-ignoriert"))
        row = await db.get(Template, out.id)
        assert row.description == "AUTO: Reise-Agent"


@pytest.mark.asyncio
async def test_update_template_regenerates_on_prompt_change(client, monkeypatch):
    from uuid import uuid4
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.db.models import User, Template
    from app.schemas.templates import AgentTemplateCreate, AgentTemplateUpdate
    from app.services import templates as tpl_svc, template_summary
    calls = {"n": 0}
    def fake(prompt): calls["n"] += 1; return _async(f"AUTO#{calls['n']}")
    monkeypatch.setattr(template_summary, "summarize_prompt", fake)
    await client.get("/artifacts")
    async with SessionLocal() as db:
        me = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        out = await tpl_svc.create_agent_template(db, me, AgentTemplateCreate(
            category="Everyday", name=f"U-{uuid4()}", prompt="alt",
            model="claude-haiku-4-5", html_template_id="classic"))
        n_after_create = calls["n"]
        await tpl_svc.update_agent_template(db, out.id, me, AgentTemplateUpdate(name="Neu"))
        assert calls["n"] == n_after_create   # kein Prompt → keine Neugenerierung
        await tpl_svc.update_agent_template(db, out.id, me, AgentTemplateUpdate(prompt="neuer prompt"))
        row = await db.get(Template, out.id)
        assert row.description.startswith("AUTO#") and calls["n"] == n_after_create + 1
