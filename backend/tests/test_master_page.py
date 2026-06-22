from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.db.session import SessionLocal


async def _owner(db):
    """Der unter AUTH_DISABLED_FOR_TESTS eingeloggte Test-User (google_sub='test-user').

    Nicht einfach der erste User der Tabelle — bei voller Suite haben frühere Tests
    bereits andere User angelegt."""
    from sqlalchemy import select

    from app.db.models import User

    return (
        await db.execute(select(User).where(User.google_sub == "test-user"))
    ).scalar_one()


async def _agent_id(client):
    a = await client.post(
        "/agents", json={"name": "Planner", "role": "x", "skills": ["a"], "visibility": "public"}
    )
    return UUID(a.json()["id"])


async def _make_instance(db, art_svc, *, owner_id, agent_id, title, content, visibility):
    from app.db.models import Visibility

    art = await art_svc.create_instance(
        db, owner_id=owner_id, agent_id=agent_id, title=title, output_type="html"
    )
    await art_svc.record_version(
        db, artifact_id=art.id, content=content, prompt="p", run_id=None
    )
    art.visibility = Visibility(visibility)
    await db.commit()
    await db.refresh(art)
    return art


@pytest.mark.asyncio
async def test_owner_sees_private_and_order_via_http(client, tmp_path, monkeypatch):
    """Owner (= AUTH_DISABLED test user) sieht eigene PRIVATE-Instanz; updated_at desc;
    html == version.content."""
    from app.services import artifacts as art_svc

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    agent_id = await _agent_id(client)

    async with SessionLocal() as db:
        owner = await _owner(db)
        first = await _make_instance(
            db, art_svc, owner_id=owner.id, agent_id=agent_id,
            title="Alt", content="<h1>alt</h1>", visibility="private",
        )
        second = await _make_instance(
            db, art_svc, owner_id=owner.id, agent_id=agent_id,
            title="Neu", content="<h1>neu</h1>", visibility="public",
        )
        owner_id = owner.id

    res = await client.get("/users/me/master")
    assert res.status_code == 200
    body = res.json()
    assert body["owner_id"] == str(owner_id)
    assert body["is_owner"] is True
    titles = [i["title"] for i in body["instances"]]
    # PRIVATE ist enthalten (Owner sieht alles)
    assert "Alt" in titles and "Neu" in titles
    # Reihenfolge updated_at desc → zuletzt erstellte/aktualisierte zuerst
    assert titles[0] == "Neu"
    # html == version.content
    neu = next(i for i in body["instances"] if i["title"] == "Neu")
    assert neu["html"] == "<h1>neu</h1>"


@pytest.mark.asyncio
async def test_anonymous_sees_only_public_via_service(client, tmp_path, monkeypatch):
    """Fremder/anonymer Betrachter sieht NUR PUBLIC/UNLISTED, nicht PRIVATE.

    Unit-Test am Service, weil unter AUTH_DISABLED_FOR_TESTS die optionale
    Auth-Dependency immer einen Test-User liefert (nie None)."""
    from app.services import artifacts as art_svc

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    agent_id = await _agent_id(client)

    async with SessionLocal() as db:
        owner = await _owner(db)
        await _make_instance(
            db, art_svc, owner_id=owner.id, agent_id=agent_id,
            title="Geheim", content="<h1>geheim</h1>", visibility="private",
        )
        await _make_instance(
            db, art_svc, owner_id=owner.id, agent_id=agent_id,
            title="Offen", content="<h1>offen</h1>", visibility="public",
        )

        # anonym (viewer=None)
        page = await art_svc.master_page(db, owner.id, None)
        assert page is not None
        assert page.is_owner is False
        titles = [i.title for i in page.instances]
        assert "Offen" in titles
        assert "Geheim" not in titles
        assert all(i.html != "<h1>geheim</h1>" for i in page.instances)

        # unbekannter Owner → None
        assert await art_svc.master_page(db, uuid4(), None) is None


@pytest.mark.asyncio
async def test_me_without_login_returns_401(client, monkeypatch):
    """`/users/me/master` ohne gültiges Token → 401 (Auth erforderlich)."""
    from app.auth import dependencies as deps

    # AUTH_DISABLED_FOR_TESTS abschalten, damit die optionale Auth ohne Token
    # tatsächlich None liefert (statt eines Test-Users).
    monkeypatch.setattr(deps.settings, "auth_disabled_for_tests", False)

    res = await client.get("/users/me/master")
    assert res.status_code == 401
