from uuid import UUID

import pytest

from app.db.session import SessionLocal


async def _agent(client):
    a = await client.post(
        "/agents", json={"name": "P", "role": "x", "skills": ["a"], "visibility": "public"}
    )
    return UUID(a.json()["id"])


@pytest.mark.asyncio
async def test_delete_artifact_removes_it(client, tmp_path, monkeypatch):
    from sqlalchemy import select

    from app.db.models import Artifact, User
    from app.services import artifacts as art_svc

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    agent_id = await _agent(client)
    async with SessionLocal() as db:
        owner = (await db.execute(select(User))).scalars().first()
        art = await art_svc.create_instance(
            db, owner_id=owner.id, agent_id=agent_id, title="Del", output_type="html",
        )
        art_id = art.id
        ok = await art_svc.delete_artifact(db, art_id, owner)
        assert ok is True
        assert await db.get(Artifact, art_id) is None
        # zweiter Versuch → False (schon weg)
        assert await art_svc.delete_artifact(db, art_id, owner) is False


@pytest.mark.asyncio
async def test_delete_artifact_rejects_non_owner(client, tmp_path, monkeypatch):
    import uuid

    from sqlalchemy import select

    from app.db.models import Artifact, User
    from app.services import artifacts as art_svc

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    agent_id = await _agent(client)
    async with SessionLocal() as db:
        owner = (await db.execute(select(User))).scalars().first()
        art = await art_svc.create_instance(
            db, owner_id=owner.id, agent_id=agent_id, title="Foreign", output_type="html",
        )
        art_id = art.id
        # Fremder Anfragender: anderer User-Datensatz mit eigener id.
        other = User(
            google_sub=f"sub-{uuid.uuid4().hex}", email=f"other-{uuid.uuid4().hex}@example.com"
        )
        db.add(other)
        await db.commit()
        await db.refresh(other)

        assert await art_svc.delete_artifact(db, art_id, other) is False
        # Artefakt existiert weiterhin.
        assert await db.get(Artifact, art_id) is not None


@pytest.mark.asyncio
async def test_delete_endpoint_204_then_404(client, tmp_path, monkeypatch):
    from sqlalchemy import select

    from app.db.models import User
    from app.services import artifacts as art_svc

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    agent_id = await _agent(client)
    async with SessionLocal() as db:
        owner = (await db.execute(select(User))).scalars().first()
        art = await art_svc.create_instance(
            db, owner_id=owner.id, agent_id=agent_id, title="D2", output_type="html",
        )
        art_id = str(art.id)
    r1 = await client.delete(f"/artifacts/{art_id}")
    assert r1.status_code == 204
    r2 = await client.delete(f"/artifacts/{art_id}")
    assert r2.status_code == 404
