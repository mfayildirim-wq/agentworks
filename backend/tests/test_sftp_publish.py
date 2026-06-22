"""Tests für den SFTP-Publish-Service (paramiko gemockt)."""

from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import select

from app.db.models import User
from app.db.session import SessionLocal
from app.services import artifact_connections as conn_svc
from app.services import sftp_publish


async def _seed_with_version(db, client, html: str | None):
    from app.services import artifacts as art_svc

    owner = (await db.execute(select(User))).scalars().first()
    resp = await client.post("/agents", json={"name": "Pub-Agent"})
    art = await art_svc.create_instance(
        db, owner_id=owner.id, agent_id=UUID(resp.json()["id"]), title="X", output_type="html"
    )
    if html is not None:
        await art_svc.record_version(db, artifact_id=art.id, content=html, prompt="", run_id=None)
    return owner, art


@pytest.mark.asyncio
async def test_publish_uploads_current_html(client, monkeypatch):
    await client.get("/artifacts")
    captured = {}

    def fake_upload(*, host, port, username, password, remote_path, data, timeout=15.0):
        captured.update(host=host, remote_path=remote_path, data=data, password=password)

    monkeypatch.setattr(sftp_publish, "_sftp_upload", fake_upload)
    async with SessionLocal() as db:
        owner, art = await _seed_with_version(db, client, "<h1>Hallo</h1>")
        await conn_svc.upsert_connection(
            db, art.id, owner.id, kind="sftp",
            config={"host": "h.example", "port": 22, "username": "u", "remote_path": "/www/index.html"},
            secret="geheim",
        )
        ok, msg = await sftp_publish.publish_artifact(db, art.id, owner.id)
    assert ok is True
    assert captured["data"] == b"<h1>Hallo</h1>"
    assert captured["remote_path"] == "/www/index.html"
    assert captured["password"] == "geheim"


@pytest.mark.asyncio
async def test_publish_without_version_fails(client, monkeypatch):
    await client.get("/artifacts")
    monkeypatch.setattr(sftp_publish, "_sftp_upload", lambda **k: None)
    async with SessionLocal() as db:
        owner, art = await _seed_with_version(db, client, None)
        await conn_svc.upsert_connection(
            db, art.id, owner.id, kind="sftp",
            config={"host": "h", "port": 22, "username": "u", "remote_path": "/p"},
            secret="x",
        )
        ok, msg = await sftp_publish.publish_artifact(db, art.id, owner.id)
    assert ok is False and "Seite" in msg


@pytest.mark.asyncio
async def test_publish_without_connection_fails(client, monkeypatch):
    await client.get("/artifacts")
    monkeypatch.setattr(sftp_publish, "_sftp_upload", lambda **k: None)
    async with SessionLocal() as db:
        owner, art = await _seed_with_version(db, client, "<h1>x</h1>")
        ok, msg = await sftp_publish.publish_artifact(db, art.id, owner.id)
    assert ok is False and "Verbindung" in msg


@pytest.mark.asyncio
async def test_publish_upload_error_is_friendly(client, monkeypatch):
    await client.get("/artifacts")

    def boom(**k):
        raise OSError("connection refused")

    monkeypatch.setattr(sftp_publish, "_sftp_upload", boom)
    async with SessionLocal() as db:
        owner, art = await _seed_with_version(db, client, "<h1>x</h1>")
        await conn_svc.upsert_connection(
            db, art.id, owner.id, kind="sftp",
            config={"host": "h", "port": 22, "username": "u", "remote_path": "/p"},
            secret="x",
        )
        ok, msg = await sftp_publish.publish_artifact(db, art.id, owner.id)
    assert ok is False
    assert "fehlgeschlagen" in msg.lower()
    assert "connection refused" not in msg
