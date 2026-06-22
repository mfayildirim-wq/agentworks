import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.db.models import User, Template


async def _agent_id(client) -> str:
    r = await client.post(
        "/agents",
        json={"name": "Planner", "role": "x", "skills": ["a"], "visibility": "public"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_create_and_get_template(client):
    aid = await _agent_id(client)
    r = await client.post(
        "/templates",
        json={
            "title": "Reiseplaner",
            "category": "travel",
            "visibility": "public",
            "output_type": "html",
            "input_schema": [
                {"key": "destination", "label": "Reiseziel", "type": "string", "required": True}
            ],
            "config": {"agent_ids": [aid], "prompt_template": "Plane {{destination}}."},
        },
    )
    assert r.status_code == 201, r.text
    t = r.json()
    assert t["title"] == "Reiseplaner"
    assert t["input_schema"][0]["key"] == "destination"
    assert t["config"]["agent_ids"] == [aid]

    got = await client.get(f"/templates/{t['id']}")
    assert got.status_code == 200
    assert got.json()["id"] == t["id"]


async def test_list_public_filter_category(client):
    aid = await _agent_id(client)
    await client.post(
        "/templates",
        json={
            "title": "T-Travel",
            "category": "travel",
            "visibility": "public",
            "config": {"agent_ids": [aid], "prompt_template": "x"},
        },
    )
    r = await client.get("/templates?category=travel")
    assert r.status_code == 200
    titles = [t["title"] for t in r.json()]
    assert "T-Travel" in titles


async def test_update_template_config_roundtrips(client):
    """Regression: config.agent_ids ist list[UUID] → JSONB-Write darf nicht an
    UUID-Serialisierung scheitern (update_template muss mode='json' nutzen)."""
    aid = await _agent_id(client)
    aid2 = await _agent_id(client)
    r = await client.post(
        "/templates",
        json={
            "title": "T",
            "visibility": "public",
            "config": {"agent_ids": [aid], "prompt_template": "alt"},
        },
    )
    tid = r.json()["id"]
    upd = await client.patch(
        f"/templates/{tid}",
        json={"config": {"agent_ids": [aid2], "prompt_template": "neu"}},
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["config"]["agent_ids"] == [aid2]
    assert upd.json()["config"]["prompt_template"] == "neu"


async def test_instance_title_label_is_the_name():
    """Bei Agent-Vorlagen ohne Eingabe-Schema ist die explizite Bezeichnung der
    Instanz-Name selbst (nicht „Vorlage - Bezeichnung")."""
    from app.services.templates import _instance_title

    assert _instance_title("Reiseplaner", [], {"label": "Mein Trip"}) == "Mein Trip"
    # Whitespace wird getrimmt
    assert _instance_title("Reiseplaner", [], {"label": "  Rom  "}) == "Rom"
    # Ohne Bezeichnung: weiterhin aus dem ersten (Pflicht-)Feld
    assert (
        _instance_title(
            "Reiseplaner", [{"key": "ziel", "required": True}], {"ziel": "Rom"}
        )
        == "Reiseplaner - Rom"
    )


async def test_render_prompt_substitutes_placeholders():
    from app.services.templates import render_prompt

    out = render_prompt(
        "Plane {{destination}} für {{days}} Tage.", {"destination": "Rom", "days": 5}
    )
    assert out == "Plane Rom für 5 Tage."


async def test_missing_required_input_rejected(client):
    aid = await _agent_id(client)
    r = await client.post(
        "/templates",
        json={
            "title": "Reiseplaner",
            "visibility": "public",
            "input_schema": [
                {"key": "destination", "label": "Ziel", "type": "string", "required": True}
            ],
            "config": {"agent_ids": [aid], "prompt_template": "Plane {{destination}}."},
        },
    )
    tid = r.json()["id"]
    bad = await client.post(f"/templates/{tid}/instantiate", json={"inputs": {}})
    assert bad.status_code == 422, bad.text


async def test_instantiate_creates_artifact_without_generation_run(client, monkeypatch):
    # Konversationelle Instanzen: KEIN Auto-Generierungslauf mehr — der Canvas entsteht
    # ausschließlich aus dem Dialog. Sonst rendert das Modell den „stell Fragen"-Prompt
    # als HTML-Fragebogen in den Canvas.
    import app.workers as workers

    sent: list = []
    monkeypatch.setattr(workers.execute_run, "send", lambda *a, **k: sent.append(a))

    aid = await _agent_id(client)
    r = await client.post(
        "/templates",
        json={
            "title": "Reiseplaner",
            "visibility": "public",
            "mode": "single",
            "input_schema": [
                {"key": "destination", "label": "Ziel", "type": "string", "required": True}
            ],
            "config": {"agent_ids": [aid], "prompt_template": "Plane {{destination}}."},
        },
    )
    tid = r.json()["id"]
    ok = await client.post(
        f"/templates/{tid}/instantiate", json={"inputs": {"destination": "Rom"}}
    )
    assert ok.status_code == 201, ok.text
    body = ok.json()
    assert body["artifact_id"] and body["template_run_id"]
    assert body["run_id"] is None  # kein Generierungslauf
    assert sent == []  # nichts dispatched

    work = await client.get(f"/works/{body['work_id']}")
    assert work.status_code == 200
    assert "Rom" in work.json()["goal"]


async def test_delete_template(client):
    aid = await _agent_id(client)
    r = await client.post(
        "/templates",
        json={
            "title": "Wegwerf",
            "visibility": "public",
            "config": {"agent_ids": [aid], "prompt_template": "x"},
        },
    )
    tid = r.json()["id"]
    d = await client.delete(f"/templates/{tid}")
    assert d.status_code == 204, d.text
    gone = await client.get(f"/templates/{tid}")
    assert gone.status_code == 404


async def test_instantiate_returns_artifact_target(client, monkeypatch, tmp_path):
    import app.workers as workers
    from app.services import artifacts as art_svc

    monkeypatch.setattr(workers.execute_run, "send", lambda *a, **k: None)
    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))

    aid = await _agent_id(client)
    r = await client.post(
        "/templates",
        json={
            "title": "Reiseplaner",
            "visibility": "public",
            "config": {"agent_ids": [aid], "prompt_template": "Plane {{x}}."},
            "input_schema": [{"key": "x", "label": "X", "type": "string", "required": True}],
        },
    )
    tid = r.json()["id"]
    ok = await client.post(f"/templates/{tid}/instantiate", json={"inputs": {"x": "Rom"}})
    body = ok.json()
    assert body["artifact_id"]
    # Instanz existiert bereits (leer) → Metadaten abrufbar, inputs gespeichert
    got = await client.get(f"/artifacts/{body['artifact_id']}")
    assert got.status_code == 200
    assert got.json()["inputs"] == {"x": "Rom"}
    assert got.json()["title"] == "Reiseplaner - Rom"


async def test_instantiate_sets_loop_config_on_work(client, monkeypatch):
    import app.workers as workers

    monkeypatch.setattr(workers.execute_run, "send", lambda *a, **k: None)

    aid = await _agent_id(client)
    r = await client.post(
        "/templates",
        json={
            "title": "Reiseplaner",
            "visibility": "public",
            "output_type": "html",
            "max_iterations": 5,
            "input_schema": [
                {"key": "destination", "label": "Ziel", "type": "string", "required": True}
            ],
            "config": {"agent_ids": [aid], "prompt_template": "Plane {{destination}}."},
        },
    )
    tid = r.json()["id"]
    ok = await client.post(
        f"/templates/{tid}/instantiate", json={"inputs": {"destination": "Rom"}}
    )
    assert ok.status_code == 201, ok.text
    work_id = ok.json()["work_id"]

    from uuid import UUID

    from app.db.models import Work
    from app.db.session import SessionLocal

    async with SessionLocal() as db:
        work = await db.get(Work, UUID(work_id))
        assert work.loop_config is not None
        assert work.loop_config["enabled"] is True
        assert work.loop_config["max_iterations"] == 5
        assert work.loop_config["max_cost_usd"] == 1.0
        assert work.loop_config["output_type"] == "html"


async def test_public_list_enriched(client, monkeypatch):
    """GET /templates/public liefert nur öffentliche Templates, mit Modell + Preis."""
    from app.services import roles
    monkeypatch.setattr(roles.settings, "admin_email", "test@local")  # Test-User = GOA → public erlaubt
    aid = await _agent_id(client)
    agent = (await client.get(f"/agents/{aid}")).json()

    pub = await client.post(
        "/templates",
        json={
            "title": "Reiseplaner",
            "description": "Plant deine Reise.",
            "category": "travel",
            "visibility": "public",
            "max_cost_usd": 2.5,
            "config": {"agent_ids": [aid], "prompt_template": "Plane {{x}}."},
        },
    )
    assert pub.status_code == 201, pub.text
    pub_id = pub.json()["id"]

    priv = await client.post(
        "/templates",
        json={"title": "Geheim", "visibility": "private"},
    )
    assert priv.status_code == 201, priv.text
    priv_id = priv.json()["id"]

    r = await client.get("/templates/public")
    assert r.status_code == 200, r.text
    items = r.json()
    by_id = {t["id"]: t for t in items}

    assert pub_id in by_id
    assert priv_id not in by_id

    card = by_id[pub_id]
    assert card["title"] == "Reiseplaner"
    assert card["price"] == 2.5
    assert card["model"] == agent["model"]
    # schlanke Sicht: keine internen Felder
    assert "owner_id" not in card
    assert "config" not in card


async def test_public_list_category_filter(client):
    aid = await _agent_id(client)
    await client.post(
        "/templates",
        json={
            "title": "Nur Travel",
            "category": "travel",
            "visibility": "public",
            "config": {"agent_ids": [aid]},
        },
    )
    r = await client.get("/templates/public?category=travel")
    assert r.status_code == 200, r.text
    assert all(t["category"] == "travel" for t in r.json())


async def test_create_agent_template_unifies(client, monkeypatch):
    """Einheitliche Agent-Vorlage: ein Aufruf -> Agent (Modell+Prompt) + Template."""
    from app.services import roles
    monkeypatch.setattr(roles.settings, "admin_email", "test@local")  # Test-User = GOA → public erlaubt
    r = await client.post(
        "/templates/agent-template",
        json={
            "name": "Reiseplaner",
            "description": "Plant Reisen als HTML-Seite.",
            "prompt": "Du bist ein Reiseplaner. Frage nach Ziel und Zeitraum und erstelle einen Reiseplan als HTML.",
            "model": "qwen2.5:3b",
            "price": 1.5,
            "category": "Everyday",
            "visibility": "public",
            "html_template_id": "classic",
        },
    )
    assert r.status_code == 201, r.text
    tpl = r.json()
    assert tpl["title"] == "Reiseplaner"
    assert tpl["max_cost_usd"] == 1.5
    aid = tpl["config"]["agent_ids"][0]

    # Agent wurde mit Prompt als System-Prompt + Modell angelegt
    agent = (await client.get(f"/agents/{aid}")).json()
    assert agent["model"] == "qwen2.5:3b"
    assert "Reiseplaner" in agent["system_prompt"]

    # taucht in der oeffentlichen Liste auf, angereichert mit model + price
    pub = (await client.get("/templates/public")).json()
    card = next(t for t in pub if t["id"] == tpl["id"])
    assert card["model"] == "qwen2.5:3b"
    assert card["price"] == 1.5


async def test_agent_template_default_model_and_icon(client):
    """Ohne Modell/Bild: lokales Default-Modell + automatisch vergebenes Emoji-Icon."""
    r = await client.post(
        "/templates/agent-template",
        json={
            "name": "Helfer",
            "prompt": "Sei hilfreich.",
            "category": "Everyday",
            "visibility": "public",
            "html_template_id": "classic",
        },
    )
    assert r.status_code == 201, r.text
    tpl = r.json()
    assert tpl["image_url"].startswith("emoji:")  # Icon automatisch vergeben
    aid = tpl["config"]["agent_ids"][0]
    agent = (await client.get(f"/agents/{aid}")).json()
    assert agent["model"] == "qwen2.5:3b"  # lokales Default-Modell


@pytest.mark.asyncio
async def test_agent_template_stores_valid_mcp_servers(client):
    from app.schemas.templates import AgentTemplateCreate
    from app.services import mcp_catalog
    from app.services.templates import create_agent_template

    await client.get("/artifacts")  # legt den Owner-User via Auth an
    async with SessionLocal() as db:
        owner = (await db.execute(select(User))).scalars().first()
        if not await mcp_catalog.get(db, "demo-everything"):
            await mcp_catalog.create(db, server_id="demo-everything", name="Demo", description="",
                transport="streamable_http", url="http://mcp-demo:8080/mcp",
                requires_credential=False, updated_by=owner.email)
        out = await create_agent_template(
            db, owner,
            AgentTemplateCreate(
                name="MCP-Demo-Agent", prompt="Du nutzt das MCP-Demo.",
                model="claude-haiku-4-5", html_template_id="classic",
                category="Everyday", mcp_servers=["demo-everything"],
            ),
        )
        tpl = await db.get(Template, out.id)
        assert tpl.config.get("mcp_servers") == ["demo-everything"]


@pytest.mark.asyncio
async def test_agent_template_rejects_unknown_mcp_server(client):
    from app.schemas.templates import AgentTemplateCreate
    from app.services.templates import create_agent_template

    await client.get("/artifacts")
    async with SessionLocal() as db:
        owner = (await db.execute(select(User))).scalars().first()
        with pytest.raises(ValueError):
            await create_agent_template(
                db, owner,
                AgentTemplateCreate(
                    name="Bad-MCP", prompt="x", model="claude-haiku-4-5",
                    html_template_id="classic", category="Everyday",
                    mcp_servers=["gibt-es-nicht"],
                ),
            )


@pytest.mark.asyncio
async def test_template_stores_valid_publish_target(client):
    from app.schemas.templates import AgentTemplateCreate
    from app.services.templates import create_agent_template
    from app.db.session import SessionLocal
    from sqlalchemy import select
    from app.db.models import User, Template

    await client.get("/artifacts")
    async with SessionLocal() as db:
        owner = (await db.execute(select(User))).scalars().first()
        out = await create_agent_template(
            db, owner,
            AgentTemplateCreate(
                name="Web-Builder", prompt="Baue eine Seite.",
                model="claude-haiku-4-5", html_template_id="classic",
                category="Everyday", publish_targets=["sftp"],
            ),
        )
        tpl = await db.get(Template, out.id)
        assert tpl.config.get("publish_targets") == ["sftp"]


@pytest.mark.asyncio
async def test_template_rejects_unknown_publish_target(client):
    from app.schemas.templates import AgentTemplateCreate
    from app.services.templates import create_agent_template
    from app.db.session import SessionLocal
    from sqlalchemy import select
    from app.db.models import User

    await client.get("/artifacts")
    async with SessionLocal() as db:
        owner = (await db.execute(select(User))).scalars().first()
        with pytest.raises(ValueError):
            await create_agent_template(
                db, owner,
                AgentTemplateCreate(
                    name="Bad", prompt="x", model="claude-haiku-4-5",
                    html_template_id="classic", category="Everyday",
                    publish_targets=["dropbox"],
                ),
            )


@pytest.mark.asyncio
async def test_template_allows_wordpress_publish_target(client):
    from app.schemas.templates import AgentTemplateCreate
    from app.services.templates import create_agent_template
    from app.db.session import SessionLocal
    from sqlalchemy import select
    from app.db.models import User, Template

    await client.get("/artifacts")
    async with SessionLocal() as db:
        owner = (await db.execute(select(User))).scalars().first()
        out = await create_agent_template(
            db, owner,
            AgentTemplateCreate(name="WP", prompt="x", model="claude-haiku-4-5",
                                html_template_id="classic", category="Everyday",
                                publish_targets=["wordpress"]),
        )
        tpl = await db.get(Template, out.id)
        assert tpl.config.get("publish_targets") == ["wordpress"]


@pytest.mark.asyncio
async def test_content_mode_roundtrip(client):
    from app.schemas.templates import AgentTemplateCreate, AgentTemplateUpdate
    from app.services.templates import (
        create_agent_template,
        get_template,
        update_agent_template,
    )

    await client.get("/artifacts")
    async with SessionLocal() as db:
        owner = (await db.execute(select(User))).scalars().first()

        # create mit content_mode="slots" -> roundtrip
        out = await create_agent_template(
            db, owner,
            AgentTemplateCreate(name="CM-Slots", prompt="x", model="claude-haiku-4-5",
                                html_template_id="classic", category="Everyday",
                                content_mode="slots"),
        )
        got = await get_template(db, out.id, owner)
        assert got.config.content_mode == "slots"

        # default-Template (html) per update auf slots umstellen
        html_tpl = await create_agent_template(
            db, owner,
            AgentTemplateCreate(name="CM-Html", prompt="x", model="claude-haiku-4-5",
                                html_template_id="classic", category="Everyday"),
        )
        got_html = await get_template(db, html_tpl.id, owner)
        assert got_html.config.content_mode == "html"
        await update_agent_template(
            db, html_tpl.id, owner, AgentTemplateUpdate(content_mode="slots")
        )
        got2 = await get_template(db, html_tpl.id, owner)
        assert got2.config.content_mode == "slots"

        # ungültiger content_mode -> ValueError (create UND update)
        with pytest.raises(ValueError):
            await create_agent_template(
                db, owner,
                AgentTemplateCreate(name="CM-Bad", prompt="x", model="claude-haiku-4-5",
                                    html_template_id="classic", category="Everyday",
                                    content_mode="bogus"),
            )
        with pytest.raises(ValueError):
            await update_agent_template(
                db, html_tpl.id, owner, AgentTemplateUpdate(content_mode="bogus")
            )


@pytest.mark.asyncio
async def test_update_agent_template_sets_mcp_servers(client):
    from app.schemas.templates import AgentTemplateCreate, AgentTemplateUpdate
    from app.services.templates import create_agent_template, update_agent_template
    from app.services import mcp_catalog
    from app.db.session import SessionLocal
    from sqlalchemy import select
    from app.db.models import User, Template

    await client.get("/artifacts")
    async with SessionLocal() as db:
        owner = (await db.execute(select(User))).scalars().first()
        if await mcp_catalog.get(db, "demo-everything") is None:
            await mcp_catalog.create(db, server_id="demo-everything", name="Demo", description="",
                transport="streamable_http", url="http://mcp-demo:8080/mcp",
                requires_credential=False, updated_by="t")
        out = await create_agent_template(
            db, owner,
            AgentTemplateCreate(name="T", prompt="x", model="claude-haiku-4-5",
                                html_template_id="classic", category="Everyday"),
        )
        await update_agent_template(db, out.id, owner, AgentTemplateUpdate(mcp_servers=["demo-everything"]))
        tpl = await db.get(Template, out.id)
        assert tpl.config.get("mcp_servers") == ["demo-everything"]
        with pytest.raises(ValueError):
            await update_agent_template(db, out.id, owner, AgentTemplateUpdate(mcp_servers=["gibt-es-nicht"]))


@pytest.mark.asyncio
async def test_instantiate_sets_output_template(client, monkeypatch, tmp_path):
    import app.workers as workers
    from app.schemas.templates import AgentTemplateCreate
    from app.services import artifacts as art_svc
    from app.services.templates import create_agent_template, instantiate
    from app.db.models import Artifact

    monkeypatch.setattr(workers.execute_run, "send", lambda *a, **k: None)
    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))

    await client.get("/artifacts")  # legt den Owner-User via Auth an
    async with SessionLocal() as db:
        owner = (await db.execute(select(User))).scalars().first()
        tpl = await create_agent_template(
            db, owner,
            AgentTemplateCreate(name="OT-Agent", prompt="x", model="claude-haiku-4-5",
                                html_template_id="classic", category="Everyday"),
        )

        # explizit gesetzt -> wird 1:1 auf das Artefakt geschrieben
        out = await instantiate(db, tpl.id, owner, {}, output_template="slots:magazine")
        art = await db.get(Artifact, out.artifact_id)
        assert art.output_template == "slots:magazine"

        # ohne output_template -> Default = zufaellige prepared-Vorlage
        out2 = await instantiate(db, tpl.id, owner, {})
        art2 = await db.get(Artifact, out2.artifact_id)
        assert art2.output_template.startswith("prepared:")
