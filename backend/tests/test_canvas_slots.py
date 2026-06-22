from uuid import UUID, uuid4

import pytest

from app.db.session import SessionLocal


async def _user_and_agent(client):
    a = await client.post(
        "/agents", json={"name": "Slotter", "role": "x", "skills": ["a"], "visibility": "public"}
    )
    return a.json()["id"]


async def _owner(db):
    from sqlalchemy import select

    from app.db.models import User

    return (await db.execute(select(User))).scalars().first()


async def _art_and_owner(client, db, *, title):
    """Erzeugt eine Instanz, die dem (ersten) User gehoert; gibt (art, owner) zurueck."""
    from app.services import artifacts as art_svc

    agent_id = await _user_and_agent(client)
    owner = await _owner(db)
    art = await art_svc.create_instance(
        db, owner_id=owner.id, agent_id=UUID(agent_id), title=title, output_type="html",
    )
    return art, owner


@pytest.mark.asyncio
async def test_upsert_merges_and_sanitizes(client, tmp_path, monkeypatch):
    from app.services import artifacts as art_svc
    from app.services import canvas_slots

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    async with SessionLocal() as db:
        art, owner = await _art_and_owner(client, db, title="merge-Instanz")
        await canvas_slots.upsert_slot(
            db, art.id, owner.id, slot_id="a", title="Alpha",
            body="<p>A</p><script>x()</script>",
        )
        await canvas_slots.upsert_slot(db, art.id, owner.id, slot_id="b", title="Beta")
        data = await canvas_slots.get_slots(db, art.id, owner.id)

    ids = {s["id"] for s in data["slots"]}
    assert ids == {"a", "b"}  # b hat a nicht ersetzt
    slot_a = next(s for s in data["slots"] if s["id"] == "a")
    assert "<script" not in slot_a["body"]
    assert "x()" not in slot_a["body"]


@pytest.mark.asyncio
async def test_remove_slot(client, tmp_path, monkeypatch):
    from app.services import artifacts as art_svc
    from app.services import canvas_slots

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    async with SessionLocal() as db:
        art, owner = await _art_and_owner(client, db, title="remove-Instanz")
        await canvas_slots.upsert_slot(db, art.id, owner.id, slot_id="a", title="Alpha")
        await canvas_slots.remove_slot(db, art.id, owner.id, "a")
        data = await canvas_slots.get_slots(db, art.id, owner.id)

    assert data["slots"] == []


@pytest.mark.asyncio
async def test_owner_enforced(client, tmp_path, monkeypatch):
    from app.services import artifacts as art_svc
    from app.services import canvas_slots

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    async with SessionLocal() as db:
        art, owner = await _art_and_owner(client, db, title="owner-Instanz")
        res = await canvas_slots.upsert_slot(
            db, art.id, uuid4(), slot_id="a", title="Alpha"
        )
        assert res is None
        data = await canvas_slots.get_slots(db, art.id, owner.id)

    assert data["slots"] == []  # kein Schreibvorgang erfolgt


@pytest.mark.asyncio
async def test_set_layout(client, tmp_path, monkeypatch):
    from app.services import artifacts as art_svc
    from app.services import canvas_slots

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    async with SessionLocal() as db:
        art, owner = await _art_and_owner(client, db, title="layout-Instanz")
        await canvas_slots.set_layout(db, art.id, owner.id, "tabs")
        data = await canvas_slots.get_slots(db, art.id, owner.id)
        assert data["layout"] == "tabs"

        with pytest.raises(ValueError):
            await canvas_slots.set_layout(db, art.id, owner.id, "x")


@pytest.mark.asyncio
async def test_upsert_creates_version_with_data_and_content(client, tmp_path, monkeypatch):
    from app.db.models import Artifact, ArtifactVersion
    from app.services import artifacts as art_svc
    from app.services import canvas_slots

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    async with SessionLocal() as db:
        art, owner = await _art_and_owner(client, db, title="version-Instanz")
        await canvas_slots.upsert_slot(
            db, art.id, owner.id, slot_id="a", title="Alpha-Titel", body="<p>A</p>",
        )
        art_orm = await db.get(Artifact, art.id)
        ver = await db.get(ArtifactVersion, art_orm.current_version_id)

    assert ver is not None
    assert ver.data is not None
    assert any(s["id"] == "a" for s in ver.data["slots"])
    assert ver.content
    assert "Alpha-Titel" in ver.content


@pytest.mark.asyncio
async def test_save_uses_instance_design_css(client, tmp_path, monkeypatch):
    """Eine Instanz eines Templates mit html_template_id='magazine' rendert mit dessen CSS."""
    from app.db.models import Artifact, ArtifactVersion
    from app.schemas.templates import AgentTemplateCreate
    from app.services import artifacts as art_svc
    from app.services import canvas_slots
    from app.services.templates import create_agent_template, instantiate

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    async with SessionLocal() as db:
        owner = await _owner(db)
        tpl = await create_agent_template(
            db, owner,
            AgentTemplateCreate(category="Everyday", 
                name="Design-CSS-Instanz", prompt="x",
                model="claude-haiku-4-5", html_template_id="magazine",
            ),
        )
        # Explizit das Slot-Design wählen; sonst würde instantiate() eine zufällige
        # prepared-Vorlage als Default setzen und der Slot-Renderer käme nicht zum Zug.
        inst = await instantiate(
            db, tpl.id, owner, {"label": "mag"}, output_template="slots:magazine"
        )
        await canvas_slots.upsert_slot(
            db, inst.artifact_id, owner.id, slot_id="a", title="Alpha", body="<p>A</p>",
        )
        art_orm = await db.get(Artifact, inst.artifact_id)
        ver = await db.get(ArtifactVersion, art_orm.current_version_id)

    assert ver is not None and ver.content
    assert "linear-gradient" in ver.content  # Magazin-CSS angewandt
    assert 'class="card"' in ver.content
    assert "Alpha" in ver.content


@pytest.mark.asyncio
async def test_save_dispatches_prepared(client, tmp_path, monkeypatch):
    """output_template='prepared:journal' rendert über page_templates (CSS inline)."""
    from app.db.models import Artifact, ArtifactVersion
    from app.services import artifacts as art_svc
    from app.services import canvas_slots

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    async with SessionLocal() as db:
        agent_id = await _user_and_agent(client)
        owner = await _owner(db)
        art = await art_svc.create_instance(
            db, owner_id=owner.id, agent_id=UUID(agent_id),
            title="prepared-Dispatch-Instanz", output_type="html",
            output_template="prepared:journal",
        )
        await canvas_slots.upsert_slot(
            db, art.id, owner.id, slot_id="title", title="T", type="text", body="Hallo",
        )
        art_orm = await db.get(Artifact, art.id)
        ver = await db.get(ArtifactVersion, art_orm.current_version_id)

    assert ver is not None and ver.content
    content = ver.content
    assert "Hallo" in content  # Platzhalter title befüllt
    assert "<style>" in content  # Journal-CSS inline
    assert "<link" not in content.lower()  # keine externe CSS-Referenz mehr
    assert 'class="journal"' in content  # Journal-Markup, nicht der Slot-Renderer


@pytest.mark.asyncio
async def test_save_dispatches_slots_design(client, tmp_path, monkeypatch):
    """output_template='slots:magazine' rendert über render_static(.., 'magazine')."""
    from app.db.models import Artifact, ArtifactVersion
    from app.services import artifacts as art_svc
    from app.services import canvas_slots

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    async with SessionLocal() as db:
        agent_id = await _user_and_agent(client)
        owner = await _owner(db)
        art = await art_svc.create_instance(
            db, owner_id=owner.id, agent_id=UUID(agent_id),
            title="slots-Design-Dispatch-Instanz", output_type="html",
            output_template="slots:magazine",
        )
        await canvas_slots.upsert_slot(
            db, art.id, owner.id, slot_id="a", title="Alpha", body="<p>A</p>",
        )
        art_orm = await db.get(Artifact, art.id)
        ver = await db.get(ArtifactVersion, art_orm.current_version_id)

    assert ver is not None and ver.content
    content = ver.content
    # Magazin-spezifisch: render_static(.., 'magazine') erzeugt Hero + Karten + Gradient-CSS.
    assert "linear-gradient" in content
    assert 'class="card"' in content
    assert "Alpha" in content
    # Nicht der prepared-Pfad: kein Journal-Markup.
    assert 'class="journal"' not in content
