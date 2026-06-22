from __future__ import annotations

from decimal import Decimal

from app.db.models import User
from app.schemas.profile import ProfileOut, ProfileUpdate


def to_out(user: User) -> ProfileOut:
    return ProfileOut(
        email=user.email,
        name=user.name,
        avatar_url=user.avatar_url,
        telegram_connected=bool(user.telegram_chat_id),
        notify_email=user.notify_email,
        notify_telegram=user.notify_telegram,
        balance_usd=user.balance_usd or Decimal("0"),
        language=getattr(user, "language", "de") or "de",
    )


async def update(db, user: User, payload: ProfileUpdate) -> ProfileOut:
    if payload.name is not None:
        user.name = payload.name
    if payload.notify_email is not None:
        user.notify_email = payload.notify_email
    if payload.notify_telegram is not None:
        user.notify_telegram = payload.notify_telegram
    if payload.language is not None:
        user.language = payload.language
    await db.commit()
    await db.refresh(user)
    return to_out(user)
