"""Tests für den WordPress-Publish-Service (httpx gemockt)."""

from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import select

from app.db.models import User
from app.db.session import SessionLocal
from app.services import artifact_connections as conn_svc
from app.services import wordpress_publish as wp


async def _seed(db, client, html):
    from app.services import artifacts as art_svc
    owner = (await db.execute(select(User))).scalars().first()
    r = await client.post("/agents", json={"name": "WP"})
    art = await art_svc.create_instance(db, owner_id=owner.id, agent_id=UUID(r.json()["id"]), title="X", output_type="html")
    if html is not None:
        await art_svc.record_version(db, artifact_id=art.id, content=html, prompt="", run_id=None)
    return owner, art


@pytest.mark.asyncio
async def test_publish_post_calls_wp_rest(client, monkeypatch):
    await client.get("/artifacts")
    captured = {}

    async def fake_post(url, *, auth, json, timeout):
        captured.update(url=url, auth=auth, json=json)
        return {"id": 77, "link": "https://x.example/?p=77"}

    monkeypatch.setattr(wp, "_wp_post", fake_post)
    async with SessionLocal() as db:
        owner, art = await _seed(db, client, "<h1>Hallo</h1>")
        await conn_svc.upsert_connection(db, art.id, owner.id, kind="wordpress",
            config={"site_url": "https://x.example", "username": "u"}, secret="apppw")
        ok, msg = await wp.publish_post(db, art.id, owner.id, title="Mein Titel", status="draft")
    assert ok is True
    assert captured["url"].endswith("/wp-json/wp/v2/posts")
    assert captured["auth"] == ("u", "apppw")
    assert captured["json"]["title"] == "Mein Titel" and "<h1>Hallo</h1>" in captured["json"]["content"]


@pytest.mark.asyncio
async def test_publish_post_without_connection(client, monkeypatch):
    await client.get("/artifacts")
    monkeypatch.setattr(wp, "_wp_post", lambda *a, **k: None)
    async with SessionLocal() as db:
        owner, art = await _seed(db, client, "<h1>x</h1>")
        ok, msg = await wp.publish_post(db, art.id, owner.id, title="t")
    assert ok is False and "Verbindung" in msg


@pytest.mark.asyncio
async def test_publish_post_error_is_friendly(client, monkeypatch):
    await client.get("/artifacts")
    async def boom(url, *, auth, json, timeout):
        raise RuntimeError("401 unauthorized apppw")
    monkeypatch.setattr(wp, "_wp_post", boom)
    async with SessionLocal() as db:
        owner, art = await _seed(db, client, "<h1>x</h1>")
        await conn_svc.upsert_connection(db, art.id, owner.id, kind="wordpress",
            config={"site_url": "https://x.example", "username": "u"}, secret="apppw")
        ok, msg = await wp.publish_post(db, art.id, owner.id, title="t")
    assert ok is False
    assert "fehlgeschlagen" in msg.lower() and "apppw" not in msg


@pytest.mark.asyncio
async def test_publish_post_updates_existing_post(client, monkeypatch):
    await client.get("/artifacts")
    captured = {}

    async def fake_post(url, *, auth, json, timeout):
        captured["url"] = url
        return {"id": 77, "link": "https://x.example/?p=77"}

    monkeypatch.setattr(wp, "_wp_post", fake_post)
    async with SessionLocal() as db:
        owner, art = await _seed(db, client, "<h1>v2</h1>")
        await conn_svc.upsert_connection(
            db, art.id, owner.id, kind="wordpress",
            config={"site_url": "https://x.example", "username": "u", "post_id": 77},
            secret="apppw",
        )
        ok, msg = await wp.publish_post(db, art.id, owner.id, title="t")
        assert ok is True
        assert captured["url"].endswith("/wp-json/wp/v2/posts/77")
        conn = await conn_svc.get_connection(db, art.id, owner.id, "wordpress")
        assert conn.config["post_id"] == 77


@pytest.mark.asyncio
async def test_post_id_survives_reconfigure(client, monkeypatch):
    await client.get("/artifacts")
    captured = {}

    async def fake_post(url, *, auth, json, timeout):
        captured["url"] = url
        return {"id": 77, "link": "https://x.example/?p=77"}

    monkeypatch.setattr(wp, "_wp_post", fake_post)
    async with SessionLocal() as db:
        owner, art = await _seed(db, client, "<h1>v1</h1>")
        # 1) erste Verbindung + erste Veröffentlichung → post_id 77 wird gemerkt
        await conn_svc.upsert_connection(db, art.id, owner.id, kind="wordpress",
            config={"site_url": "https://x.example", "username": "u"}, secret="apppw")
        ok, _ = await wp.publish_post(db, art.id, owner.id, title="t1")
        assert ok is True
        # 2) Nutzer ändert die Verbindung (Form sendet nur site_url/username, KEIN post_id)
        await conn_svc.upsert_connection(db, art.id, owner.id, kind="wordpress",
            config={"site_url": "https://x.example", "username": "u2"}, secret="")
        # 3) erneute Veröffentlichung muss DENSELBEN Beitrag aktualisieren (URL .../posts/77)
        ok2, _ = await wp.publish_post(db, art.id, owner.id, title="t2")
        assert ok2 is True
        assert captured["url"].endswith("/wp-json/wp/v2/posts/77")
        conn = await conn_svc.get_connection(db, art.id, owner.id, "wordpress")
        assert conn.config["post_id"] == 77 and conn.config["username"] == "u2"
