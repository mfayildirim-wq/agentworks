"""Tests für das Telegram-Verbinden (Link-Token → chat_id, idempotent)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db.models import User
from app.db.session import SessionLocal
from app.services.notify import telegram_link as tl


async def _test_user(db) -> User:
    return (
        await db.execute(select(User).where(User.google_sub == "test-user"))
    ).scalars().first()


@pytest.mark.asyncio
async def test_link_token_then_start_connects_chat_id(client):
    await client.get("/profile")  # bootstrap Test-User
    async with SessionLocal() as db:
        token = await tl.create_link_token(db, await _test_user(db))
        assert token

    async with SessionLocal() as db:
        linked = await tl.handle_start(db, token, "999")
        assert linked is not None
        assert linked.telegram_chat_id == "999"

    # Token ist verbraucht → derselbe /start verbindet nicht erneut.
    async with SessionLocal() as db:
        assert await tl.handle_start(db, token, "888") is None


@pytest.mark.asyncio
async def test_handle_start_unknown_token_is_ignored(client):
    async with SessionLocal() as db:
        assert await tl.handle_start(db, "kein-gueltiges-token", "1") is None


@pytest.mark.asyncio
async def test_disconnect_clears_chat_id(client):
    await client.get("/profile")
    async with SessionLocal() as db:
        user = await _test_user(db)
        user.telegram_chat_id = "555"
        await db.commit()
        await tl.disconnect(db, user)
        assert user.telegram_chat_id is None
