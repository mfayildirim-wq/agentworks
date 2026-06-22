"""Tests für den generalisierten Verbindungs-Service (config + secret, mehrere kinds)."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.core import crypto
from app.db.models import User
from app.db.session import SessionLocal
from app.services import artifact_connections as conn_svc


async def _seed(db, client):
    from app.services import artifacts as art_svc

    owner = (await db.execute(select(User))).scalars().first()
    resp = await client.post("/agents", json={"name": "Conn-Agent"})
    assert resp.status_code == 201, resp.text
    art = await art_svc.create_instance(
        db, owner_id=owner.id, agent_id=UUID(resp.json()["id"]), title="X", output_type="html"
    )
    return owner, art


@pytest.mark.asyncio
async def test_upsert_encrypts_secret_and_safe_out_hides_it(client):
    await client.get("/artifacts")
    async with SessionLocal() as db:
        owner, art = await _seed(db, client)
        conn = await conn_svc.upsert_connection(
            db, art.id, owner.id, kind="wordpress",
            config={"site_url": "https://x.example", "username": "u"}, secret="apppw",
        )
        assert conn is not None
        assert conn.secret_encrypted != "apppw"
        assert crypto.decrypt(conn.secret_encrypted) == "apppw"
        safe = conn_svc.to_safe_out(conn)
        assert safe == {"kind": "wordpress",
                        "config": {"site_url": "https://x.example", "username": "u"},
                        "configured": True}
        assert "secret" not in safe and "secret_encrypted" not in safe


@pytest.mark.asyncio
async def test_empty_secret_on_update_keeps_old(client):
    await client.get("/artifacts")
    async with SessionLocal() as db:
        owner, art = await _seed(db, client)
        await conn_svc.upsert_connection(db, art.id, owner.id, kind="wordpress",
                                         config={"site_url": "a"}, secret="alt")
        await conn_svc.upsert_connection(db, art.id, owner.id, kind="wordpress",
                                         config={"site_url": "b"}, secret="")
        conn = await conn_svc.get_connection(db, art.id, owner.id, "wordpress")
        assert conn.config["site_url"] == "b"
        assert crypto.decrypt(conn.secret_encrypted) == "alt"


@pytest.mark.asyncio
async def test_multiple_kinds_per_instance(client):
    await client.get("/artifacts")
    async with SessionLocal() as db:
        owner, art = await _seed(db, client)
        await conn_svc.upsert_connection(db, art.id, owner.id, kind="sftp",
                                         config={"host": "h"}, secret="p1")
        await conn_svc.upsert_connection(db, art.id, owner.id, kind="wordpress",
                                         config={"site_url": "s"}, secret="p2")
        rows = await conn_svc.list_connections(db, art.id, owner.id)
        assert {r.kind for r in rows} == {"sftp", "wordpress"}


@pytest.mark.asyncio
async def test_foreign_instance_returns_none(client):
    await client.get("/artifacts")
    async with SessionLocal() as db:
        owner, art = await _seed(db, client)
        out = await conn_svc.upsert_connection(db, art.id, uuid4(), kind="sftp",
                                               config={"host": "h"}, secret="x")
        assert out is None
