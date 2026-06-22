def test_visibility_has_friends():
    from app.db.models import Visibility
    assert Visibility.FRIENDS.value == "friends"


def test_friendship_table_exists():
    from app.db.models import Friendship
    assert "requester_id" in Friendship.__table__.c


import pytest
from uuid import uuid4
from sqlalchemy import select
from app.db.session import SessionLocal
from app.db.models import User
from app.services import friends


async def _two_users(db):
    me = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
    other = User(email=f"o-{uuid4()}@x.de", google_sub=str(uuid4()), name="Bob")
    db.add(other); await db.flush()
    return me, other

@pytest.mark.asyncio
async def test_request_accept_and_are_friends(client):
    await client.get("/artifacts")
    async with SessionLocal() as db:
        me, other = await _two_users(db)
        await db.commit()
        fr = await friends.send_request(db, me.id, other.email)
        assert fr is not None and fr.status == "pending"
        assert await friends.are_friends(db, me.id, other.id) is False
        ok = await friends.accept(db, fr.id, other.id)   # nur addressee darf
        assert ok is True
        assert await friends.are_friends(db, me.id, other.id) is True
        names = [u.name for u in await friends.list_friends(db, me.id)]
        assert "Bob" in names

@pytest.mark.asyncio
async def test_no_self_and_no_duplicate(client):
    await client.get("/artifacts")
    async with SessionLocal() as db:
        me = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        assert await friends.send_request(db, me.id, me.email) is None  # keine Selbst-Freundschaft
        other = User(email=f"d-{uuid4()}@x.de", google_sub=str(uuid4()), name="Di")
        db.add(other); await db.commit()
        a = await friends.send_request(db, me.id, other.email)
        b = await friends.send_request(db, me.id, other.email)  # Duplikat → keine zweite Zeile
        assert a is not None and b is not None and a.id == b.id

@pytest.mark.asyncio
async def test_search_users_excludes_self(client):
    await client.get("/artifacts")
    async with SessionLocal() as db:
        me = (await db.execute(select(User).where(User.google_sub=="test-user"))).scalars().first()
        other = User(email=f"search-{uuid4()}@x.de", google_sub=str(uuid4()), name="Suchbar")
        db.add(other); await db.commit()
        res = await friends.search_users(db, "Suchbar", exclude_id=me.id)
        assert any(u.name == "Suchbar" for u in res)
        res2 = await friends.search_users(db, "test@local", exclude_id=me.id)
        assert all(u.id != me.id for u in res2)

@pytest.mark.asyncio
async def test_request_endpoint(client):
    await client.get("/artifacts")
    async with SessionLocal() as db:
        other = User(email=f"ep-{uuid4()}@x.de", google_sub=str(uuid4()), name="Endpoint")
        db.add(other); await db.commit()
        email = other.email
    resp = await client.post("/friends/request", json={"email_or_name": email})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


async def _other_with_instance(db, content="<h1>shared</h1>"):
    from uuid import uuid4 as _uuid4

    from app.db.models import Agent, User as _User
    from app.services import artifacts as art_svc

    other = _User(email=f"fr-{_uuid4()}@x.de", google_sub=str(_uuid4()), name="Owner")
    db.add(other)
    await db.flush()
    agent = Agent(owner_id=other.id, name="A")
    db.add(agent)
    await db.flush()
    art = await art_svc.create_instance(
        db, owner_id=other.id, agent_id=agent.id, title="T", output_type="html"
    )
    await art_svc.record_version(
        db, artifact_id=art.id, content=content, prompt="", run_id=None
    )
    return other, art


@pytest.mark.asyncio
async def test_public_html_friends_visibility(client, tmp_path, monkeypatch):
    from app.services import artifacts as art_svc
    from app.db.models import Artifact, Visibility

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    await client.get("/artifacts")
    async with SessionLocal() as db:
        me = (await db.execute(select(User).where(User.google_sub == "test-user"))).scalars().first()
        other, art = await _other_with_instance(db)
        # me und other befreunden
        fr = await friends.send_request(db, me.id, other.email)
        await friends.accept(db, fr.id, other.id)
        assert await friends.are_friends(db, me.id, other.id) is True

        # visibility = friends
        art_orm = await db.get(Artifact, art.id)
        art_orm.visibility = Visibility.FRIENDS
        await db.commit()
        # Freund sieht es, Anonym nicht
        assert await art_svc.public_html(db, art.id, viewer=me) == "<h1>shared</h1>"
        assert await art_svc.public_html(db, art.id, viewer=None) is None

        # private → Nicht-Besitzer (auch Freund) sieht nichts
        art_orm = await db.get(Artifact, art.id)
        art_orm.visibility = Visibility.PRIVATE
        await db.commit()
        assert await art_svc.public_html(db, art.id, viewer=me) is None
        assert await art_svc.public_html(db, art.id, viewer=None) is None
        # Besitzer sieht seine private Instanz
        assert await art_svc.public_html(db, art.id, viewer=other) == "<h1>shared</h1>"

        # public → für jeden, auch anonym
        art_orm = await db.get(Artifact, art.id)
        art_orm.visibility = Visibility.PUBLIC
        await db.commit()
        assert await art_svc.public_html(db, art.id, viewer=None) == "<h1>shared</h1>"


@pytest.mark.asyncio
async def test_shared_artifacts_list(client, tmp_path, monkeypatch):
    from app.services import artifacts as art_svc
    from app.db.models import Artifact, Visibility

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    await client.get("/artifacts")
    async with SessionLocal() as db:
        me = (await db.execute(select(User).where(User.google_sub == "test-user"))).scalars().first()
        # befreundete "other" mit Instanz
        other, art = await _other_with_instance(db)
        fr = await friends.send_request(db, me.id, other.email)
        await friends.accept(db, fr.id, other.id)
        assert await friends.are_friends(db, me.id, other.id) is True
        art_orm = await db.get(Artifact, art.id)
        art_orm.visibility = Visibility.FRIENDS
        await db.commit()
        friend_art_id = art.id

        # Nicht-Freund mit friends-Instanz → darf NICHT auftauchen
        stranger, stranger_art = await _other_with_instance(db)
        stranger_orm = await db.get(Artifact, stranger_art.id)
        stranger_orm.visibility = Visibility.FRIENDS
        await db.commit()
        stranger_art_id = stranger_art.id

    resp = await client.get("/artifacts/shared")
    assert resp.status_code == 200
    ids = [row["artifact_id"] for row in resp.json()]
    assert str(friend_art_id) in ids
    assert str(stranger_art_id) not in ids

    # private → nicht mehr in der Liste
    async with SessionLocal() as db:
        from app.db.models import Artifact, Visibility

        art_orm = await db.get(Artifact, friend_art_id)
        art_orm.visibility = Visibility.PRIVATE
        await db.commit()
    resp = await client.get("/artifacts/shared")
    assert resp.status_code == 200
    ids = [row["artifact_id"] for row in resp.json()]
    assert str(friend_art_id) not in ids


@pytest.mark.asyncio
async def test_public_html_friends_denies_non_friend(client, tmp_path, monkeypatch):
    from app.services import artifacts as art_svc
    from app.db.models import Artifact, Visibility

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    await client.get("/artifacts")
    async with SessionLocal() as db:
        me = (await db.execute(select(User).where(User.google_sub == "test-user"))).scalars().first()
        other, art = await _other_with_instance(db)
        # KEINE Freundschaft
        art_orm = await db.get(Artifact, art.id)
        art_orm.visibility = Visibility.FRIENDS
        await db.commit()
        assert await friends.are_friends(db, me.id, other.id) is False
        assert await art_svc.public_html(db, art.id, viewer=me) is None


@pytest.mark.asyncio
async def test_friends_list_id_is_friendship_id_and_delete_works(client):
    """GET /friends liefert die friendship_id (nicht User-id), sodass DELETE /friends/{id}
    den Freund tatsächlich entfernt."""
    await client.get("/artifacts")
    async with SessionLocal() as db:
        me = (await db.execute(select(User).where(User.google_sub == "test-user"))).scalars().first()
        other = User(email=f"del-{uuid4()}@x.de", google_sub=str(uuid4()), name="DelBob")
        db.add(other); await db.commit()
        fr = await friends.send_request(db, me.id, other.email)
        await friends.accept(db, fr.id, other.id)
        fid = str(fr.id)

    r = await client.get("/friends")
    assert r.status_code == 200
    row = next((x for x in r.json() if x["name"] == "DelBob"), None)
    assert row is not None and row["id"] == fid     # id == friendship_id

    d = await client.delete(f"/friends/{fid}")
    assert d.status_code == 200 and d.json()["ok"] is True
    async with SessionLocal() as db:
        assert await friends.are_friends(db, me.id, other.id) is False
