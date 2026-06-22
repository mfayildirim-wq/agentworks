"""Tests für den Instanz-Datei-Upload (Basis)."""

from __future__ import annotations

import io
from uuid import UUID, uuid4

import pytest
from starlette.datastructures import Headers, UploadFile

from app.db.session import SessionLocal
from app.services import artifact_files as files_svc


async def _seed_owner_and_artifact(db, client):
    from sqlalchemy import select

    from app.db.models import User
    from app.services import artifacts as art_svc

    owner = (await db.execute(select(User))).scalars().first()
    resp = await client.post("/agents", json={"name": "Datei-Agent"})
    assert resp.status_code == 201, resp.text
    agent_id = UUID(resp.json()["id"])
    art = await art_svc.create_instance(
        db, owner_id=owner.id, agent_id=agent_id, title="X", output_type="html"
    )
    return owner, art


def _upload(name: str, content_type: str, data: bytes) -> UploadFile:
    return UploadFile(
        file=io.BytesIO(data), filename=name, headers=Headers({"content-type": content_type})
    )


@pytest.mark.asyncio
async def test_save_files_writes_disk_and_row(client, tmp_path, monkeypatch):
    monkeypatch.setattr(files_svc.settings, "media_root", str(tmp_path))
    from app.services import artifacts as art_svc

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    await client.get("/artifacts")
    async with SessionLocal() as db:
        owner, art = await _seed_owner_and_artifact(db, client)
        saved = await files_svc.save_files(
            db, art.id, owner.id, [_upload("strand.jpg", "image/jpeg", b"abc")]
        )
        assert saved is not None and len(saved) == 1
        row = saved[0]
        assert row.filename == "strand.jpg"
        assert row.url.startswith(f"/media/artifacts/{owner.id}/{art.id}/")
        assert row.url.endswith(".jpg")
        assert row.size == 3
        disk = files_svc._disk_path(row.url)
        import os

        assert os.path.exists(disk)


@pytest.mark.asyncio
async def test_save_files_foreign_owner_returns_none(client, tmp_path, monkeypatch):
    monkeypatch.setattr(files_svc.settings, "media_root", str(tmp_path))
    await client.get("/artifacts")
    async with SessionLocal() as db:
        _owner, art = await _seed_owner_and_artifact(db, client)
        out = await files_svc.save_files(
            db, art.id, uuid4(), [_upload("x.png", "image/png", b"x")]
        )
        assert out is None


@pytest.mark.asyncio
async def test_attachments_context_lists_only_instance_files(client, tmp_path, monkeypatch):
    monkeypatch.setattr(files_svc.settings, "media_root", str(tmp_path))
    await client.get("/artifacts")
    async with SessionLocal() as db:
        owner, art = await _seed_owner_and_artifact(db, client)
        saved = await files_svc.save_files(
            db, art.id, owner.id, [_upload("reise.pdf", "application/pdf", b"%PDF-")]
        )
        block = await files_svc.attachments_context(db, art.id, [saved[0].id])
        assert "Angehängte Dateien" in block
        assert "reise.pdf" in block
        assert await files_svc.attachments_context(db, art.id, []) == ""
        assert await files_svc.attachments_context(db, art.id, [uuid4()]) == ""


@pytest.mark.asyncio
async def test_delete_file_removes_row_and_disk(client, tmp_path, monkeypatch):
    monkeypatch.setattr(files_svc.settings, "media_root", str(tmp_path))
    import os

    await client.get("/artifacts")
    async with SessionLocal() as db:
        owner, art = await _seed_owner_and_artifact(db, client)
        saved = await files_svc.save_files(
            db, art.id, owner.id, [_upload("a.png", "image/png", b"xy")]
        )
        fid = saved[0].id
        disk = files_svc._disk_path(saved[0].url)
        assert os.path.exists(disk)
        assert await files_svc.delete_file(db, art.id, fid, uuid4()) is False
        assert await files_svc.delete_file(db, uuid4(), fid, owner.id) is False
        assert await files_svc.delete_file(db, art.id, fid, owner.id) is True
        assert not os.path.exists(disk)
        rows = await files_svc.list_files(db, art.id, owner.id)
        assert rows == []


@pytest.mark.asyncio
async def test_save_files_rejects_unsupported_type(client, tmp_path, monkeypatch):
    from fastapi import HTTPException

    monkeypatch.setattr(files_svc.settings, "media_root", str(tmp_path))
    await client.get("/artifacts")
    async with SessionLocal() as db:
        owner, art = await _seed_owner_and_artifact(db, client)
        with pytest.raises(HTTPException) as exc:
            await files_svc.save_files(
                db, art.id, owner.id,
                [_upload("evil.bin", "application/octet-stream", b"x")],
            )
        assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_post_chat_message_appends_attachment_block(client, tmp_path, monkeypatch):
    monkeypatch.setattr(files_svc.settings, "media_root", str(tmp_path))
    # Worker nicht wirklich anstoßen — nur den gespeicherten Nachrichtentext prüfen.
    from app.services import artifact_chat as chat_svc

    import app.workers as workers

    monkeypatch.setattr(workers.execute_chat_turn, "send", lambda *a, **k: None)

    await client.get("/artifacts")
    async with SessionLocal() as db:
        owner, art = await _seed_owner_and_artifact(db, client)
        saved = await files_svc.save_files(
            db, art.id, owner.id, [_upload("strand.jpg", "image/jpeg", b"abc")]
        )
        ok = await chat_svc.post_chat_message(
            db, art.id, owner.id, "Bau mir das Reisebuch", file_ids=[saved[0].id]
        )
        assert ok is True

        from sqlalchemy import select

        from app.db.models import ArtifactMessage

        rows = await db.execute(
            select(ArtifactMessage).where(ArtifactMessage.artifact_id == art.id)
        )
        user_msg = next(m for m in rows.scalars().all() if m.role == "user")
        assert "Bau mir das Reisebuch" in user_msg.content
        assert "Angehängte Dateien" in user_msg.content
        assert saved[0].url in user_msg.content
        assert user_msg.file_ids == [str(saved[0].id)]


@pytest.mark.asyncio
async def test_post_chat_message_without_files_unchanged(client, tmp_path, monkeypatch):
    from app.services import artifact_chat as chat_svc

    import app.workers as workers

    monkeypatch.setattr(workers.execute_chat_turn, "send", lambda *a, **k: None)
    monkeypatch.setattr(files_svc.settings, "media_root", str(tmp_path))

    await client.get("/artifacts")
    async with SessionLocal() as db:
        owner, art = await _seed_owner_and_artifact(db, client)
        ok = await chat_svc.post_chat_message(db, art.id, owner.id, "Nur Text")
        assert ok is True
        from sqlalchemy import select

        from app.db.models import ArtifactMessage

        rows = await db.execute(
            select(ArtifactMessage).where(ArtifactMessage.artifact_id == art.id)
        )
        user_msg = next(m for m in rows.scalars().all() if m.role == "user")
        assert user_msg.content == "Nur Text"
        assert user_msg.file_ids is None


@pytest.mark.asyncio
async def test_upload_list_delete_via_api(client, tmp_path, monkeypatch):
    monkeypatch.setattr(files_svc.settings, "media_root", str(tmp_path))
    from app.services import artifacts as art_svc

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))

    a = await client.post("/agents", json={"name": "API-Agent"})
    agent_id = a.json()["id"]
    async with SessionLocal() as db:
        from sqlalchemy import select

        from app.db.models import User

        owner = (await db.execute(select(User))).scalars().first()
        art = await art_svc.create_instance(
            db, owner_id=owner.id, agent_id=UUID(agent_id), title="X", output_type="html"
        )
        art_id = str(art.id)

    up = await client.post(
        f"/artifacts/{art_id}/files",
        files=[("files", ("strand.jpg", b"abc", "image/jpeg"))],
    )
    assert up.status_code == 201, up.text
    body = up.json()
    assert len(body) == 1 and body[0]["filename"] == "strand.jpg"
    fid = body[0]["id"]

    lst = await client.get(f"/artifacts/{art_id}/files")
    assert lst.status_code == 200 and len(lst.json()) == 1

    dele = await client.delete(f"/artifacts/{art_id}/files/{fid}")
    assert dele.status_code == 204
    lst2 = await client.get(f"/artifacts/{art_id}/files")
    assert lst2.json() == []


@pytest.mark.asyncio
async def test_delete_artifact_removes_file_folder(client, tmp_path, monkeypatch):
    import os

    monkeypatch.setattr(files_svc.settings, "media_root", str(tmp_path))
    from app.services import artifacts as art_svc

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    await client.get("/artifacts")
    async with SessionLocal() as db:
        from sqlalchemy import select

        from app.db.models import User

        owner = (await db.execute(select(User))).scalars().first()
        _o, art = await _seed_owner_and_artifact(db, client)
        saved = await files_svc.save_files(
            db, art.id, owner.id, [_upload("a.png", "image/png", b"xy")]
        )
        folder = os.path.dirname(files_svc._disk_path(saved[0].url))
        assert os.path.isdir(folder)
        assert await art_svc.delete_artifact(db, art.id, owner) is True
        assert not os.path.isdir(folder)


@pytest.mark.asyncio
async def test_save_files_rejects_over_25mb(client, tmp_path, monkeypatch):
    monkeypatch.setattr(files_svc.settings, "media_root", str(tmp_path))
    await client.get("/artifacts")
    async with SessionLocal() as db:
        owner, art = await _seed_owner_and_artifact(db, client)
        big = b"x" * (25 * 1024 * 1024 + 1)
        with pytest.raises(Exception) as exc:
            await files_svc.save_files(
                db, art.id, owner.id, [_upload("gross.txt", "text/plain", big)]
            )
        assert getattr(exc.value, "status_code", None) == 400
        assert "25" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_attachments_context_inlines_document_text(client, tmp_path, monkeypatch):
    monkeypatch.setattr(files_svc.settings, "media_root", str(tmp_path))
    await client.get("/artifacts")
    async with SessionLocal() as db:
        owner, art = await _seed_owner_and_artifact(db, client)
        saved = await files_svc.save_files(
            db, art.id, owner.id,
            [_upload("brief.txt", "text/plain", "Sehr geehrte Damen".encode())],
        )
        ctx = await files_svc.attachments_context(db, art.id, [saved[0].id])
        assert "brief.txt" in ctx
        assert "Sehr geehrte Damen" in ctx  # Inhalt, nicht nur die URL


@pytest.mark.asyncio
async def test_attachments_context_lists_image_url(client, tmp_path, monkeypatch):
    monkeypatch.setattr(files_svc.settings, "media_root", str(tmp_path))
    await client.get("/artifacts")
    async with SessionLocal() as db:
        owner, art = await _seed_owner_and_artifact(db, client)
        saved = await files_svc.save_files(
            db, art.id, owner.id, [_upload("strand.jpg", "image/jpeg", b"abc")]
        )
        ctx = await files_svc.attachments_context(db, art.id, [saved[0].id])
        assert saved[0].url in ctx
        assert "img" in ctx.lower()  # Hinweis auf Einbau per <img>


@pytest.mark.asyncio
async def test_attachments_context_empty_for_no_ids(client, tmp_path, monkeypatch):
    monkeypatch.setattr(files_svc.settings, "media_root", str(tmp_path))
    await client.get("/artifacts")
    async with SessionLocal() as db:
        owner, art = await _seed_owner_and_artifact(db, client)
        assert await files_svc.attachments_context(db, art.id, []) == ""


@pytest.mark.asyncio
async def test_attachments_context_truncates_long_document(client, tmp_path, monkeypatch):
    monkeypatch.setattr(files_svc.settings, "media_root", str(tmp_path))
    await client.get("/artifacts")
    async with SessionLocal() as db:
        owner, art = await _seed_owner_and_artifact(db, client)
        long_text = ("A" * 20000).encode()
        saved = await files_svc.save_files(
            db, art.id, owner.id, [_upload("lang.txt", "text/plain", long_text)]
        )
        ctx = await files_svc.attachments_context(db, art.id, [saved[0].id])
        assert "… [gekürzt]" in ctx
        assert ctx.count("A") <= files_svc._MAX_DOC_CHARS + 50  # gekürzt, nicht voll
