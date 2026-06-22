"""Telegram-Verbinden: Link-Token erzeugen, /start verarbeiten, trennen.

Flow: Profil erzeugt ein Einmal-Token → Nutzer öffnet t.me/<bot>?start=<token> und
drückt Start → der Poller ruft handle_start(token, chat_id) → chat_id wird gespeichert,
Token verbraucht. Idempotent: unbekanntes/verbrauchtes Token → None (ignoriert).
"""

from __future__ import annotations

import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


async def create_link_token(db: AsyncSession, user: User) -> str:
    token = secrets.token_urlsafe(16)
    user.telegram_link_token = token
    await db.commit()
    return token


async def handle_start(db: AsyncSession, token: str, chat_id: str) -> User | None:
    if not token:
        return None
    user = (
        await db.execute(select(User).where(User.telegram_link_token == token))
    ).scalar_one_or_none()
    if user is None:
        return None
    # Vorherigen Besitzer dieses Chats lösen (chat_id ist nicht unique) — sonst hätten
    # zwei Konten dieselbe chat_id und der Verteiler könnte das falsche auflösen.
    prev = (await db.execute(select(User).where(
        User.telegram_chat_id == str(chat_id), User.id != user.id))).scalars().all()
    for p in prev:
        p.telegram_chat_id = None
    user.telegram_chat_id = str(chat_id)
    user.telegram_link_token = None
    await db.commit()
    await db.refresh(user)
    return user


async def disconnect(db: AsyncSession, user: User) -> None:
    user.telegram_chat_id = None
    user.telegram_link_token = None
    await db.commit()
