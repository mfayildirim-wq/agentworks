from __future__ import annotations
import pytest
from app.services import output_commands as oc


def test_modes_present():
    keys = {c["key"] for c in oc.kinds("page")}
    # Tab-Modi + Listen-/Abschnitts-Modi; legacy "neuer_tab" bleibt entfernt.
    assert {"hinzufuegen", "ueberarbeiten", "ueberschreiben", "liste", "oben", "unten"} <= keys
    assert "neuer_tab" not in keys
    assert oc.is_mode("hinzufuegen") and oc.is_mode("liste") and oc.is_mode("oben")
    assert not oc.is_mode("neuer_tab")


def test_default_mode_is_hinzufuegen_first():
    modes = [c for c in oc.kinds("page") if c["kind"] == "mode"]
    assert modes[0]["key"] == "hinzufuegen"


def test_registry_actions_present():
    keys = [c["key"] for c in oc.kinds("page")]
    assert {"abschnitte", "refresh"} <= set(keys)
    assert "verlauf" not in keys   # Versionen liegen jetzt im Instanz-Konfig-Popup
    assert not oc.is_mode("refresh")


@pytest.mark.asyncio
async def test_set_output_mode_endpoint(client):
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.db.models import User, Agent, Artifact, Visibility, TemplateOutput
    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        ag = Agent(owner_id=u.id, name="A", role="r"); db.add(ag); await db.flush()
        art = Artifact(owner_id=u.id, agent_id=ag.id, title="X",
                       output_type=TemplateOutput("html"), visibility=Visibility.PRIVATE)
        db.add(art); await db.flush(); await db.commit(); aid = str(art.id)
    r = await client.put(f"/artifacts/{aid}/output-mode", json={"mode": "ueberarbeiten"})
    assert r.status_code == 200 and r.json()["mode"] == "ueberarbeiten"
    r = await client.put(f"/artifacts/{aid}/output-mode", json={"mode": "quatsch"})
    assert r.status_code == 200 and r.json()["mode"] == "ueberschreiben"
    r = await client.get(f"/artifacts/{aid}/commands")
    assert r.status_code == 200 and any(c["key"] == "hinzufuegen" for c in r.json())


@pytest.mark.asyncio
async def test_view_and_restore_version(client):
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.db.models import User, Agent, Artifact, Visibility, TemplateOutput
    from app.services import artifacts as art_svc
    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        ag = Agent(owner_id=u.id, name="A", role="r"); db.add(ag); await db.flush()
        art = Artifact(owner_id=u.id, agent_id=ag.id, title="X",
                       output_type=TemplateOutput("html"), visibility=Visibility.PRIVATE)
        db.add(art); await db.flush()
        v1 = await art_svc.record_version(db, artifact_id=art.id, content="<p>EINS</p>", prompt="1", run_id=None)
        await art_svc.record_version(db, artifact_id=art.id, content="<p>ZWEI</p>", prompt="2", run_id=None)
        await db.commit(); aid = str(art.id); v1id = str(v1.id)
    # ansehen
    r = await client.get(f"/artifacts/{aid}/versions/{v1id}")
    assert r.status_code == 200 and "EINS" in r.json()["content"]
    # wiederherstellen → neue current-Version mit altem Inhalt
    r = await client.post(f"/artifacts/{aid}/versions/{v1id}/restore")
    assert r.status_code == 200
    view = (await client.get(f"/artifacts/{aid}")).json()
    assert "EINS" in view["current_content"]
    # ArtifactView.versions liefert ids
    assert all("id" in v for v in view["versions"])
