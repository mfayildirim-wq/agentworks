"""Tests für den DB-gestützten MCP-Katalog."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db.models import User
from app.db.session import SessionLocal
from app.services import mcp_catalog


@pytest.mark.asyncio
async def test_create_get_isvalid_and_disabled(client):
    await client.get("/artifacts")
    async with SessionLocal() as db:
        admin = (await db.execute(select(User))).scalars().first()
        s = await mcp_catalog.create(
            db, server_id="my-srv", name="My", description="d",
            transport="sse", url="http://x/sse", requires_credential=False,
            updated_by=admin.email,
        )
        assert s.server_id == "my-srv"
        assert (await mcp_catalog.get(db, "my-srv")) is not None
        assert await mcp_catalog.is_valid(db, "my-srv") is True
        await mcp_catalog.update(db, "my-srv", enabled=False, updated_by=admin.email)
        assert await mcp_catalog.is_valid(db, "my-srv") is False
        assert (await mcp_catalog.get(db, "my-srv")).enabled is False


@pytest.mark.asyncio
async def test_unknown_is_invalid(client):
    await client.get("/artifacts")
    async with SessionLocal() as db:
        assert await mcp_catalog.is_valid(db, "nope") is False
        assert await mcp_catalog.get(db, "nope") is None


@pytest.mark.asyncio
async def test_delete(client):
    await client.get("/artifacts")
    async with SessionLocal() as db:
        admin = (await db.execute(select(User))).scalars().first()
        await mcp_catalog.create(db, server_id="tmp", name="t", description="",
                                 transport="sse", url="http://x", requires_credential=False,
                                 updated_by=admin.email)
        assert await mcp_catalog.delete(db, "tmp") is True
        assert await mcp_catalog.get(db, "tmp") is None


@pytest.mark.asyncio
async def test_create_with_auth_fields_roundtrip(client):
    await client.get("/artifacts")
    async with SessionLocal() as db:
        admin = (await db.execute(select(User))).scalars().first()
        s = await mcp_catalog.create(
            db, server_id="notion", name="Notion", description="d",
            transport="sse", url="http://x/sse", requires_credential=True,
            updated_by=admin.email,
            auth_header="Authorization", auth_value_template="Bearer {secret}",
            secret_label="Notion-Token",
        )
        assert s.auth_header == "Authorization"
        assert s.auth_value_template == "Bearer {secret}"
        assert s.secret_label == "Notion-Token"
        out = mcp_catalog.to_out(s)
        assert out["auth_header"] == "Authorization"
        assert out["auth_value_template"] == "Bearer {secret}"
        assert out["secret_label"] == "Notion-Token"


@pytest.mark.asyncio
async def test_auth_template_must_contain_secret_placeholder(client):
    await client.get("/artifacts")
    async with SessionLocal() as db:
        admin = (await db.execute(select(User))).scalars().first()
        with pytest.raises(ValueError):
            await mcp_catalog.create(
                db, server_id="bad1", name="Bad", description="",
                transport="sse", url="http://x", requires_credential=True,
                updated_by=admin.email, auth_value_template="Bearer xxx",
            )


@pytest.mark.asyncio
async def test_auth_template_rejects_foreign_placeholder(client):
    await client.get("/artifacts")
    async with SessionLocal() as db:
        admin = (await db.execute(select(User))).scalars().first()
        with pytest.raises(ValueError):
            await mcp_catalog.create(
                db, server_id="bad2", name="Bad", description="",
                transport="sse", url="http://x", requires_credential=True,
                updated_by=admin.email, auth_value_template="Bearer {secret} {other}",
            )
