from __future__ import annotations
import pytest
from app.services import output_placement as op


def test_overwrite_returns_new():
    html, data = op.apply("ueberschreiben", current_data=None, current_content="<p>alt</p>",
                          new_output="<p>neu</p>")
    assert html == "<p>neu</p>" and data is None


def test_hinzufuegen_first_result_is_single_page():
    # Erstes Ergebnis (kein Vorinhalt) bleibt eine Einzelseite, noch keine Tabs.
    html, data = op.apply("hinzufuegen", current_data=None, current_content="",
                          new_output="<h1>Rom</h1>")
    assert html == "<h1>Rom</h1>" and data is None


def test_hinzufuegen_second_result_makes_tabs_new_left():
    html, data = op.apply("hinzufuegen", current_data=None, current_content="<p>ALT</p>",
                          new_output="<p>NEU</p>")
    assert data["layout"] == "tabs" and len(data["slots"]) == 2
    by_order = sorted(data["slots"], key=lambda s: s["order"])
    assert "NEU" in by_order[0]["body"]   # neuester links (kleinste order)
    assert "ALT" in by_order[1]["body"]


def test_hinzufuegen_prepends_on_existing_tabs():
    cur = {"layout": "tabs", "slots": [
        {"id": "a", "title": "T1", "order": 0, "body": "<p>EINS</p>"},
        {"id": "b", "title": "T2", "order": 1, "body": "<p>ZWEI</p>"}]}
    html, data = op.apply("hinzufuegen", current_data=cur, current_content="",
                          new_output="<p>DREI</p>")
    assert len(data["slots"]) == 3
    assert sorted(data["slots"], key=lambda s: s["order"])[0]["body"] == "<p>DREI</p>"


def test_ueberarbeiten_replaces_active_tab():
    cur = {"layout": "tabs", "slots": [
        {"id": "a", "title": "T1", "order": 0, "body": "<p>NEUSTE</p>"},
        {"id": "b", "title": "T2", "order": 1, "body": "<p>ALT</p>"}]}
    html, data = op.apply("ueberarbeiten", current_data=cur, current_content="",
                          new_output="<p>ERSETZT</p>")
    assert len(data["slots"]) == 2
    active = sorted(data["slots"], key=lambda s: s["order"])[0]
    assert active["body"] == "<p>ERSETZT</p>"          # aktiver (linker) Tab ersetzt
    assert sorted(data["slots"], key=lambda s: s["order"])[1]["body"] == "<p>ALT</p>"


def test_ueberarbeiten_on_single_page_replaces():
    html, data = op.apply("ueberarbeiten", current_data=None, current_content="<p>ALT</p>",
                          new_output="<p>NEU</p>")
    assert html == "<p>NEU</p>" and data is None


def test_output_mode_prompt_hinzufuegen_asks_full_result():
    p = op.output_mode_prompt("hinzufuegen")
    assert "vollständig" in p.lower() or "komplett" in p.lower()
    assert op.output_mode_prompt("ueberschreiben") == ""


def test_default_title_is_date_like():
    _, data = op.apply("hinzufuegen", current_data=None, current_content="<p>x</p>", new_output="<p>y</p>")
    new = [s for s in data["slots"] if "y" in s["body"]][0]
    assert "." in new["title"] and ":" in new["title"]   # DD.MM.YYYY HH:MM


def test_output_mode_prompt():
    assert op.output_mode_prompt("ueberschreiben") == ""
    assert "vollständig" in op.output_mode_prompt("hinzufuegen").lower()
    assert "Tab" in op.output_mode_prompt("ueberarbeiten")


@pytest.mark.asyncio
async def test_record_version_placed_hinzufuegen(client):
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.db.models import User, Agent, Artifact, Visibility, TemplateOutput
    from app.services import artifacts as art_svc
    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        ag = Agent(owner_id=u.id, name="A", role="r"); db.add(ag); await db.flush()
        art = Artifact(owner_id=u.id, agent_id=ag.id, title="X", output_mode="hinzufuegen",
                       output_type=TemplateOutput("html"), visibility=Visibility.PRIVATE)
        db.add(art); await db.flush()
        await art_svc.record_version(db, artifact_id=art.id, content="<p>ALT</p>", prompt="1", run_id=None)
        v = await art_svc.record_version_placed(db, artifact_id=art.id, content="<p>NEU</p>", prompt="2", run_id=None)
        await db.commit()
        assert v is not None and v.data is not None and "NEU" in v.content and "ALT" in v.content


@pytest.mark.asyncio
async def test_new_artifact_default_mode_is_hinzufuegen(client):
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.db.models import User, Agent, Artifact, Visibility, TemplateOutput
    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.google_sub == "test-user"))).scalars().first()
        ag = Agent(owner_id=u.id, name="A", role="r"); db.add(ag); await db.flush()
        art = Artifact(owner_id=u.id, agent_id=ag.id, title="X",
                       output_type=TemplateOutput("html"), visibility=Visibility.PRIVATE)
        db.add(art); await db.flush()
        await db.refresh(art)
        assert art.output_mode == "hinzufuegen"


def test_title_from_heading():
    assert op._title_from("<h2>Mein Rezept</h2><p>x</p>") == "Mein Rezept"
    assert "." in op._title_from("<p>kein titel</p>")   # Datum-Fallback


def test_liste_first_result_is_single_page():
    html, data = op.apply("liste", current_data=None, current_content="",
                          new_output="<h2>Pasta</h2><p>a</p>")
    assert html == "<h2>Pasta</h2><p>a</p>" and data is None


def test_liste_second_result_linked_list_new_on_top():
    html, data = op.apply("liste", current_data=None, current_content="<h2>Pasta</h2><p>a</p>",
                          new_output="<h2>Pizza</h2><p>b</p>")
    assert data["layout"] == "liste" and len(data["slots"]) == 2
    by_order = sorted(data["slots"], key=lambda s: s["order"])
    assert by_order[0]["title"] == "Pizza"   # neuer Eintrag oben
    assert by_order[1]["title"] == "Pasta"   # Start-Slot aus Überschrift benannt
    assert 'class="toc"' in html and 'href="#' in html   # verlinktes Verzeichnis


def test_unten_appends_at_bottom():
    cur = {"layout": "liste", "slots": [
        {"id": "a", "title": "Pasta", "order": 0, "body": "<h2>Pasta</h2>"}]}
    html, data = op.apply("unten", current_data=cur, current_content="",
                          new_output="<h2>Pizza</h2>")
    by_order = sorted(data["slots"], key=lambda s: s["order"])
    assert by_order[-1]["title"] == "Pizza"


def test_output_mode_prompt_liste():
    assert "Verzeichnis" in op.output_mode_prompt("liste")
    assert "Verzeichnis" in op.output_mode_prompt("oben")
