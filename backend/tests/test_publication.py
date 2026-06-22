def test_template_publish_status_default():
    from app.db.models import Template
    assert Template.__table__.c.publish_status.default.arg == ""
    assert Template.__table__.c.publish_note.default.arg == ""


import pytest
from uuid import uuid4
from sqlalchemy import select
from app.db.session import SessionLocal
from app.db.models import User, Template, Visibility
from app.schemas.templates import AgentTemplateCreate
from app.services import templates as tpl_svc


async def _my_private_template(db):
    me = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
    t = await tpl_svc.create_agent_template(db, me, AgentTemplateCreate(
        category="Everyday", name=f"Pub-{uuid4()}", prompt="x",
        model="claude-haiku-4-5", html_template_id="classic", visibility=Visibility.PRIVATE))
    return me, t

@pytest.mark.asyncio
async def test_request_publication_sets_pending(client):
    await client.get("/artifacts")
    async with SessionLocal() as db:
        me, t = await _my_private_template(db)
        # TemplateOut traegt das Feld (default "" bei frischem Template).
        assert hasattr(t, "publish_status") and t.publish_status == ""
        ok = await tpl_svc.request_publication(db, t.id, me)
        assert ok is True
        row = await db.get(Template, t.id)
        assert row.publish_status == "pending"
        # TemplateOut.model_validate uebernimmt den ORM-Wert.
        out = await tpl_svc.get_template(db, t.id, me)
        assert out.publish_status == "pending"

@pytest.mark.asyncio
async def test_request_publication_owner_only_and_private_only(client):
    await client.get("/artifacts")
    async with SessionLocal() as db:
        me, t = await _my_private_template(db)
        other = User(email=f"x-{uuid4()}@x.de", google_sub=str(uuid4()), name="X")
        db.add(other); await db.commit()
        assert await tpl_svc.request_publication(db, t.id, other) is False   # nicht Besitzer
        row = await db.get(Template, t.id); row.visibility = Visibility.PUBLIC
        await db.commit()
        assert await tpl_svc.request_publication(db, t.id, me) is False       # nicht privat

@pytest.mark.asyncio
async def test_admin_approve_and_reject(client, monkeypatch):
    monkeypatch.setattr("app.auth.dependencies.settings.admin_email", "test@local")  # Test-User = GOA → is_admin
    await client.get("/artifacts")
    async with SessionLocal() as db:
        me, t = await _my_private_template(db)
        await tpl_svc.request_publication(db, t.id, me)
        tid = str(t.id)
    # Liste
    r = await client.get("/admin/publication-requests")
    assert r.status_code == 200 and any(x["id"] == tid for x in r.json())
    # Genehmigen
    a = await client.post(f"/admin/templates/{tid}/approve")
    assert a.status_code == 200 and a.json()["ok"] is True
    async with SessionLocal() as db:
        row = await db.get(Template, __import__("uuid").UUID(tid))
        assert row.visibility == Visibility.PUBLIC and row.publish_status == ""

@pytest.mark.asyncio
async def test_admin_endpoints_forbidden_for_normal_user(client):
    # Test-User ist NICHT GOA/Admin (kein monkeypatch) → 403
    r = await client.get("/admin/publication-requests")
    assert r.status_code == 403
