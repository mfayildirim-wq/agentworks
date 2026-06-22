# backend/tests/test_template_commands.py
import pytest


def _agent_template_payload(commands):
    from app.schemas.templates import AgentTemplateCreate

    return AgentTemplateCreate(
        name="Reiseplaner",
        prompt="Plane eine Reise.",
        category="Planner",
        html_template_id="",
        commands=commands,
    )


@pytest.mark.asyncio
async def test_create_agent_template_persists_valid_command(client, monkeypatch):
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.db.models import User
    from app.services import templates as tsvc, html_templates

    monkeypatch.setattr(html_templates, "is_valid", lambda x: True)

    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub == "test-user"))).scalars().first()
        payload = _agent_template_payload(
            [
                {
                    "key": "neuesziel",
                    "label": "Neues Ziel",
                    "instruction": "Erstelle einen Reiseführer für {input}.",
                    "mode": "hinzufuegen",
                }
            ]
        )
        out = await tsvc.create_agent_template(db, u, payload)
        cmds = (out.config.commands if hasattr(out.config, "commands") else out.config["commands"])
        # TemplateOut.config is a TemplateConfig model
        assert len(out.config.commands) == 1
        assert out.config.commands[0].key == "neuesziel"
        assert out.config.commands[0].mode == "hinzufuegen"
        assert out.config.commands[0].instruction == "Erstelle einen Reiseführer für {input}."


@pytest.mark.asyncio
async def test_create_agent_template_rejects_invalid_mode(client, monkeypatch):
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.db.models import User
    from app.services import templates as tsvc, html_templates

    monkeypatch.setattr(html_templates, "is_valid", lambda x: True)
    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub == "test-user"))).scalars().first()
        payload = _agent_template_payload(
            [{"key": "x", "label": "X", "instruction": "tu was", "mode": "kaputt"}]
        )
        with pytest.raises(ValueError):
            await tsvc.create_agent_template(db, u, payload)


@pytest.mark.asyncio
async def test_create_agent_template_rejects_system_key(client, monkeypatch):
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.db.models import User
    from app.services import templates as tsvc, html_templates

    monkeypatch.setattr(html_templates, "is_valid", lambda x: True)
    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub == "test-user"))).scalars().first()
        payload = _agent_template_payload(
            [{"key": "liste", "label": "Liste", "instruction": "tu was", "mode": "hinzufuegen"}]
        )
        with pytest.raises(ValueError):
            await tsvc.create_agent_template(db, u, payload)


@pytest.mark.asyncio
async def test_create_agent_template_rejects_duplicate_keys(client, monkeypatch):
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.db.models import User
    from app.services import templates as tsvc, html_templates

    monkeypatch.setattr(html_templates, "is_valid", lambda x: True)
    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub == "test-user"))).scalars().first()
        payload = _agent_template_payload(
            [
                {"key": "a", "label": "A", "instruction": "x", "mode": "hinzufuegen"},
                {"key": "a", "label": "A2", "instruction": "y", "mode": "oben"},
            ]
        )
        with pytest.raises(ValueError):
            await tsvc.create_agent_template(db, u, payload)


@pytest.mark.asyncio
async def test_update_agent_template_sets_commands(client, monkeypatch):
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.db.models import User
    from app.schemas.templates import AgentTemplateUpdate
    from app.services import templates as tsvc, html_templates

    monkeypatch.setattr(html_templates, "is_valid", lambda x: True)
    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub == "test-user"))).scalars().first()
        created = await tsvc.create_agent_template(db, u, _agent_template_payload([]))
        upd = AgentTemplateUpdate(
            commands=[{"key": "neu", "label": "Neu", "instruction": "tu was", "mode": "oben"}]
        )
        out = await tsvc.update_agent_template(db, created.id, u, upd)
        assert len(out.config.commands) == 1
        assert out.config.commands[0].key == "neu"
        # invalid mode on update is rejected
        bad = AgentTemplateUpdate(
            commands=[{"key": "z", "label": "Z", "instruction": "x", "mode": "kaputt"}]
        )
        with pytest.raises(ValueError):
            await tsvc.update_agent_template(db, created.id, u, bad)


@pytest.mark.asyncio
async def test_commands_endpoint_appends_template_commands(client):
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.db.models import User, Template, Agent, Visibility, TemplateOutput
    from app.services import templates as tsvc

    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub == "test-user"))).scalars().first()
        ag = Agent(owner_id=u.id, name="Planner", role="r")
        db.add(ag)
        await db.flush()
        tpl = Template(
            owner_id=u.id,
            title="Reiseplaner",
            output_type=TemplateOutput.HTML,
            visibility=Visibility.PUBLIC,
            config={
                "agent_ids": [str(ag.id)],
                "prompt_template": "Plane {ziel}",
                "commands": [
                    {
                        "key": "neuesziel",
                        "label": "Neues Ziel",
                        "instruction": "Reiseführer für {input}.",
                        "mode": "hinzufuegen",
                    }
                ],
            },
        )
        db.add(tpl)
        await db.flush()
        await db.commit()
        resp = await tsvc.instantiate(db, tpl.id, u, {"ziel": "London"}, output_template="agent")
        art_id = resp.artifact_id

    r = await client.get(f"/artifacts/{art_id}/commands")
    assert r.status_code == 200
    data = r.json()
    system = [c for c in data if c["kind"] in ("mode", "action")]
    template = [c for c in data if c["kind"] == "template"]
    assert len(system) >= 1
    assert len(template) == 1
    tc = template[0]
    assert tc["key"] == "neuesziel"
    assert tc["label"] == "Neues Ziel"
    assert tc["mode"] == "hinzufuegen"
    assert tc["instruction"] == "Reiseführer für {input}."
    # Template commands come AFTER the system commands.
    assert data.index(tc) > max(data.index(c) for c in system)


@pytest.mark.asyncio
async def test_commands_endpoint_without_template_only_system(client):
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.db.models import User, Agent
    from app.services import artifacts as artifact_svc

    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub == "test-user"))).scalars().first()
        ag = Agent(owner_id=u.id, name="Solo", role="r")
        db.add(ag)
        await db.flush()
        art = await artifact_svc.create_instance(
            db,
            owner_id=u.id,
            agent_id=ag.id,
            title="Solo",
            output_type="html",
            template_id=None,
            inputs={},
            output_template="agent",
            output_mode="hinzufuegen",
        )
        art_id = art.id

    r = await client.get(f"/artifacts/{art_id}/commands")
    assert r.status_code == 200
    data = r.json()
    assert all(c["kind"] in ("mode", "action") for c in data)
    assert not any(c["kind"] == "template" for c in data)
