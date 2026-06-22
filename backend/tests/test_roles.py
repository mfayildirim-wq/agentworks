import pytest
from uuid import uuid4
from sqlalchemy import select
from app.db.session import SessionLocal
from app.db.models import User
from app.services import roles


class _U:
    def __init__(self, email, role=""): self.email = email; self.role = role

def test_is_goa_and_is_admin(monkeypatch):
    monkeypatch.setattr(roles.settings, "admin_email", "boss@x.de")
    assert roles.is_goa(_U("boss@x.de")) is True
    assert roles.is_goa(_U("u@x.de")) is False
    assert roles.is_admin(_U("boss@x.de")) is True          # GOA ist auch admin
    assert roles.is_admin(_U("u@x.de", role="admin")) is True
    assert roles.is_admin(_U("u@x.de", role="")) is False

@pytest.mark.asyncio
async def test_set_role_and_search(client):
    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = User(email=f"r-{uuid4()}@x.de", google_sub=str(uuid4()), name="RoleBob")
        db.add(u); await db.commit()
        ok = await roles.set_role(db, u.id, "admin")
        assert ok is True
        u2 = await db.get(User, u.id); assert u2.role == "admin"
        assert await roles.set_role(db, u.id, "boss") is False   # ungültiger Wert
        res = await roles.search_users(db, "RoleBob")
        assert any(x.name == "RoleBob" for x in res)

@pytest.mark.asyncio
async def test_template_gating_normal_user_forced_private(client, monkeypatch):
    from app.db.models import Visibility
    from app.schemas.templates import AgentTemplateCreate
    from app.services import templates as tpl_svc
    from sqlalchemy import select
    from app.db.models import User
    await client.get("/artifacts")
    async with SessionLocal() as db:
        me = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        # me ist NICHT GOA (admin_email != test@local) und role="" → normaler User
        t = await tpl_svc.create_agent_template(db, me, AgentTemplateCreate(
            category="Everyday", name=f"Gate-{__import__('uuid').uuid4()}",
            prompt="x", model="claude-haiku-4-5", html_template_id="classic",
            visibility=Visibility.PUBLIC))
        # normaler User → trotz public-Wunsch privat erzwungen
        from app.db.models import Template
        row = await db.get(Template, t.id)
        assert row.visibility == Visibility.PRIVATE

@pytest.mark.asyncio
async def test_template_gating_admin_may_public(client, monkeypatch):
    from app.db.models import Visibility, User, Template
    from app.schemas.templates import AgentTemplateCreate
    from app.services import templates as tpl_svc, roles
    from sqlalchemy import select
    await client.get("/artifacts")
    monkeypatch.setattr(roles.settings, "admin_email", "test@local")  # Test-User = GOA
    async with SessionLocal() as db:
        me = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        t = await tpl_svc.create_agent_template(db, me, AgentTemplateCreate(
            category="Everyday", name=f"Gate2-{__import__('uuid').uuid4()}",
            prompt="x", model="claude-haiku-4-5", html_template_id="classic",
            visibility=Visibility.PUBLIC))
        row = await db.get(Template, t.id)
        assert row.visibility == Visibility.PUBLIC

@pytest.mark.asyncio
async def test_admin_users_requires_goa(client):
    # Test-User ist NICHT GOA (admin_email=admin@example.com) → 403
    r = await client.get("/admin/users?q=x")
    assert r.status_code == 403

@pytest.mark.asyncio
async def test_goa_can_set_admin(client, monkeypatch):
    from app.api import admin as admin_api  # für settings-Patch
    monkeypatch.setattr("app.auth.dependencies.settings.admin_email", "test@local")
    from uuid import uuid4
    from sqlalchemy import select
    from app.db.models import User
    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = User(email=f"mk-{uuid4()}@x.de", google_sub=str(uuid4()), name="MkAdmin")
        db.add(u); await db.commit(); uid = str(u.id)
    r = await client.put(f"/admin/users/{uid}/role", json={"role": "admin"})
    assert r.status_code == 200 and r.json()["ok"] is True
    s = await client.get("/admin/users?q=MkAdmin")
    assert s.status_code == 200 and any(x["role"] == "admin" for x in s.json())


@pytest.mark.asyncio
async def test_update_template_cannot_publish_as_normal_user(client):
    """PATCH-Pfad: normaler User darf ein privates Template nicht auf public heben."""
    from app.db.models import Visibility, User, Template
    from app.schemas.templates import AgentTemplateCreate, TemplateUpdate
    from app.services import templates as tpl_svc
    from sqlalchemy import select
    await client.get("/artifacts")
    async with SessionLocal() as db:
        me = (await db.execute(select(User).where(User.google_sub == "test-user"))).scalars().first()
        t = await tpl_svc.create_agent_template(db, me, AgentTemplateCreate(
            category="Everyday", name=f"Upd-{uuid4()}", prompt="x",
            model="claude-haiku-4-5", html_template_id="classic", visibility=Visibility.PRIVATE))
        await tpl_svc.update_template(db, t.id, me, TemplateUpdate(visibility=Visibility.PUBLIC))
        row = await db.get(Template, t.id)
        assert row.visibility == Visibility.PRIVATE   # Gating greift auch im PATCH


@pytest.mark.asyncio
async def test_create_agent_cannot_be_public_as_normal_user(client):
    from app.db.models import Visibility, User, Agent
    from app.schemas.agents import AgentCreate
    from app.services import agents as ag_svc
    from sqlalchemy import select
    await client.get("/artifacts")
    async with SessionLocal() as db:
        me = (await db.execute(select(User).where(User.google_sub == "test-user"))).scalars().first()
        out = await ag_svc.create_agent(db, me, AgentCreate(
            name=f"PubAg-{uuid4()}", role="r", visibility=Visibility.PUBLIC))
        ag = await db.get(Agent, out.id)
        assert ag.visibility == Visibility.PRIVATE


@pytest.mark.asyncio
async def test_set_role_invalid_value_422(client, monkeypatch):
    monkeypatch.setattr("app.auth.dependencies.settings.admin_email", "test@local")
    from uuid import uuid4 as _u
    from sqlalchemy import select
    from app.db.models import User
    await client.get("/artifacts")
    async with SessionLocal() as db:
        u = User(email=f"inv-{_u()}@x.de", google_sub=str(_u()), name="Inv")
        db.add(u); await db.commit(); uid = str(u.id)
    r = await client.put(f"/admin/users/{uid}/role", json={"role": "superadmin"})
    assert r.status_code == 422
