import pytest
from uuid import UUID, uuid4
from sqlalchemy import select
from app.db.session import SessionLocal
from app.db.models import User, Rating
from app.services import agents as ag_svc


async def _agent(client):
    """Agent + eine Instanz davon (Bewerten setzt eine eigene Instanz voraus)."""
    r = await client.post("/agents", json={"name": "Rate-Me"})
    aid = UUID(r.json()["id"])
    from app.services import artifacts as art_svc
    async with SessionLocal() as db:
        me = (await db.execute(select(User).where(User.google_sub == "test-user"))).scalars().first()
        await art_svc.create_instance(db, owner_id=me.id, agent_id=aid, title="i", output_type="html")
    return aid

@pytest.mark.asyncio
async def test_rate_requires_owned_instance(client):
    """Ohne eigene Instanz des Agenten → keine Bewertung möglich."""
    await client.get("/artifacts")
    r = await client.post("/agents", json={"name": "NoInstance"})
    aid = UUID(r.json()["id"])
    async with SessionLocal() as db:
        me = (await db.execute(select(User).where(User.google_sub == "test-user"))).scalars().first()
        assert await ag_svc.rate_agent(db, aid, me.id, 5) is None   # keine Instanz → None

@pytest.mark.asyncio
async def test_rate_agent_upsert_and_range(client):
    await client.get("/artifacts")
    aid = await _agent(client)
    async with SessionLocal() as db:
        me = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        assert await ag_svc.rate_agent(db, aid, me.id, 6) is None      # ungültig
        r1 = await ag_svc.rate_agent(db, aid, me.id, 4); assert r1.stars == 4
        r2 = await ag_svc.rate_agent(db, aid, me.id, 5)                 # Upsert
        rows = (await db.execute(select(Rating).where(Rating.agent_id==aid))).scalars().all()
        assert len(rows) == 1 and rows[0].stars == 5
        avg, cnt = (await ag_svc._ratings_map(db, [aid])).get(aid, (0,0))
        assert avg == 5.0 and cnt == 1

@pytest.mark.asyncio
async def test_rating_endpoint(client):
    aid = await _agent(client)
    r = await client.post(f"/agents/{aid}/rating", json={"stars": 4, "comment": "gut"})
    assert r.status_code == 200 and r.json()["ratings_count"] == 1 and r.json()["my_stars"] == 4
    bad = await client.post(f"/agents/{aid}/rating", json={"stars": 9})
    assert bad.status_code == 422


@pytest.mark.asyncio
async def test_public_templates_enriched_and_sorted(client, monkeypatch):
    from app.services import roles
    monkeypatch.setattr(roles.settings, "admin_email", "test@local")  # test-user = GOA → public
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.db.models import User, Visibility, Artifact, TemplateOutput, Template
    from app.schemas.templates import AgentTemplateCreate
    from app.services import templates as tpl_svc, agents as ag_svc
    await client.get("/artifacts")
    async with SessionLocal() as db:
        me = (await db.execute(select(User).where(User.google_sub == "test-user"))).scalars().first()
        t = await tpl_svc.create_agent_template(db, me, AgentTemplateCreate(
            category="Everyday", name=f"Rated-{uuid4()}", prompt="x",
            model="claude-haiku-4-5", html_template_id="classic", visibility=Visibility.PUBLIC))
    # Hol das Template + seinen primären Agenten frisch und bewerte/instanziiere:
    async with SessionLocal() as db:
        row = await db.get(Template, t.id)
        aid = row.config["agent_ids"][0]
        aid = aid if isinstance(aid, UUID) else UUID(str(aid))
        me = (await db.execute(select(User).where(User.google_sub == "test-user"))).scalars().first()
        # Instanzen ZUERST (Bewerten setzt eine eigene Instanz voraus), dann bewerten.
        for _ in range(2):
            db.add(Artifact(owner_id=me.id, agent_id=aid, template_id=t.id,
                            output_type=TemplateOutput("html"), visibility=Visibility.PRIVATE, title="i"))
        await db.commit()
        await ag_svc.rate_agent(db, aid, me.id, 5)
        out = await tpl_svc.list_public_templates(db, sort="popular")
        mine = next(x for x in out if x.id == t.id)
        assert mine.works_count == 2 and mine.ratings_count == 1 and mine.avg_stars == 5.0


@pytest.mark.asyncio
async def test_artifact_view_prefills_own_rating(client):
    from app.services import artifacts as art_svc
    await client.get("/artifacts")
    aid = await _agent(client)
    async with SessionLocal() as db:
        owner = (await db.execute(
            select(User).where(User.google_sub == "test-user"))).scalars().first()
        art = await art_svc.create_instance(
            db, owner_id=owner.id, agent_id=aid, title="Inst", output_type="html")
        await ag_svc.rate_agent(db, aid, owner.id, 4)
        view = await art_svc.get_view(db, art.id, owner)
    assert view is not None
    assert view.my_stars == 4
    assert view.agent_rating_avg == 4.0
    assert view.agent_rating_count == 1


@pytest.mark.asyncio
async def test_get_template_metrics_and_reviews(client, monkeypatch):
    from app.services import roles
    monkeypatch.setattr(roles.settings, "admin_email", "test@local")
    from uuid import UUID, uuid4
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.db.models import User, Visibility, Artifact, TemplateOutput, Template
    from app.schemas.templates import AgentTemplateCreate
    from app.services import templates as tpl_svc, agents as ag_svc
    await client.get("/artifacts")
    async with SessionLocal() as db:
        me = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        t = await tpl_svc.create_agent_template(db, me, AgentTemplateCreate(
            category="Everyday", name=f"Det-{uuid4()}", prompt="x",
            model="claude-haiku-4-5", html_template_id="classic", visibility=Visibility.PUBLIC))
        row = await db.get(Template, t.id)
        aid = row.config["agent_ids"][0]; aid = aid if isinstance(aid, UUID) else UUID(str(aid))
        # 2 Instanzen, dann bewerten (mit + ohne Kommentar geht nur 1×/Nutzer → 1 Review)
        for _ in range(2):
            db.add(Artifact(owner_id=me.id, agent_id=aid, template_id=t.id,
                            output_type=TemplateOutput("html"), visibility=Visibility.PRIVATE, title="i"))
        await db.commit()
        await ag_svc.rate_agent(db, aid, me.id, 5, "super agent")
        # get_template-Kennzahlen
        out = await tpl_svc.get_template(db, t.id, me)
        assert out.works_count == 2 and out.ratings_count == 1 and out.avg_stars == 5.0
        # Reviews (mit Kommentar, Name, Datum)
        revs = await ag_svc.list_reviews(db, aid)
        assert len(revs) == 1 and revs[0]["comment"] == "super agent" and revs[0]["stars"] == 5
        assert revs[0]["user_name"]  # nicht leer (Fallback „Nutzer")

@pytest.mark.asyncio
async def test_reviews_only_with_comment(client):
    from uuid import UUID
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.db.models import User
    from app.services import agents as ag_svc
    aid = await _agent(client)   # legt Agent + Instanz an (Slice-1-Helper)
    async with SessionLocal() as db:
        me = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        await ag_svc.rate_agent(db, aid, me.id, 4)   # OHNE Kommentar
        revs = await ag_svc.list_reviews(db, aid)
        assert revs == []   # zählt zum Schnitt, aber nicht gelistet


@pytest.mark.asyncio
async def test_public_search_q(client, monkeypatch):
    from app.services import roles
    monkeypatch.setattr(roles.settings, "admin_email", "test@local")
    from uuid import uuid4
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.db.models import User, Visibility
    from app.schemas.templates import AgentTemplateCreate
    from app.services import templates as tpl_svc
    await client.get("/artifacts")
    tag = uuid4().hex[:8]
    async with SessionLocal() as db:
        me = (await db.execute(select(User).where(User.google_sub == "test-user"))).scalars().first()
        # Treffer NUR über den Prompt (Titel/Beschreibung enthalten den Tag NICHT):
        await tpl_svc.create_agent_template(db, me, AgentTemplateCreate(
            category="Everyday", name="Such Agent", description="ein agent",
            prompt=f"Spezialwort {tag} im Prompt", model="claude-haiku-4-5",
            html_template_id="classic", visibility=Visibility.PUBLIC))
        out = await tpl_svc.list_public_templates(db, q=tag)
        assert len(out) == 1 and out[0].title == "Such Agent"
        # Prompt darf NICHT im Output stehen (tokenfrei):
        assert not hasattr(out[0], "prompt") and not hasattr(out[0], "prompt_template")
        # Nicht-Treffer:
        assert await tpl_svc.list_public_templates(db, q="garantiert-kein-treffer-xyz") == []
        # leeres q = unverändert (>=1):
        assert len(await tpl_svc.list_public_templates(db, q="")) >= 1
