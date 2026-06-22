# backend/tests/test_template_output_mode.py
import pytest


@pytest.mark.asyncio
async def test_instantiate_uses_template_default_output_mode(client):
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.db.models import User, Template, Artifact, Agent, Visibility, TemplateOutput
    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub == "test-user"))).scalars().first()
        ag = Agent(owner_id=u.id, name="Planner", role="r"); db.add(ag); await db.flush()
        tpl = Template(owner_id=u.id, title="Reiseplaner", output_type=TemplateOutput.HTML,
                       visibility=Visibility.PUBLIC,
                       config={"agent_ids": [str(ag.id)], "prompt_template": "Plane {ziel}",
                               "default_output_mode": "ueberarbeiten"})
        db.add(tpl); await db.flush(); await db.commit()
        from app.services import templates as tsvc
        resp = await tsvc.instantiate(db, tpl.id, u, {"ziel": "London"}, output_template="agent")
        art = await db.get(Artifact, resp.artifact_id)
        assert art.output_mode == "ueberarbeiten"


@pytest.mark.asyncio
async def test_instantiate_defaults_to_hinzufuegen_when_template_silent(client):
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.db.models import User, Template, Artifact, Agent, Visibility, TemplateOutput
    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub == "test-user"))).scalars().first()
        ag = Agent(owner_id=u.id, name="Koch", role="r"); db.add(ag); await db.flush()
        tpl = Template(owner_id=u.id, title="Rezepte", output_type=TemplateOutput.HTML,
                       visibility=Visibility.PUBLIC,
                       config={"agent_ids": [str(ag.id)], "prompt_template": "Koche {x}"})
        db.add(tpl); await db.flush(); await db.commit()
        from app.services import templates as tsvc
        resp = await tsvc.instantiate(db, tpl.id, u, {"x": "Pasta"}, output_template="agent")
        art = await db.get(Artifact, resp.artifact_id)
        assert art.output_mode == "hinzufuegen"
