"""Dispatcher: schickt eine Benachrichtigung über die aktiven, konfigurierten Kanäle
des Nutzers. Best-effort — ein fehlschlagender Kanal stoppt die anderen nicht."""

from __future__ import annotations

from app.core.logging import logger
from app.core.settings import get_settings
from app.db.models import User
from app.services.notify import channels

settings = get_settings()


async def notify_user(user: User, subject: str, text: str, url: str) -> int:
    """Versendet an alle passenden Kanäle. Gibt die Anzahl erfolgreicher Sends zurück."""
    sent = 0

    if user.notify_email and settings.smtp_host and user.email:
        try:
            await channels.send_email(user.email, subject, text, url)
            sent += 1
        except Exception:
            logger.exception("notify-email-failed", user=str(user.id))

    if user.notify_telegram and settings.telegram_bot_token and user.telegram_chat_id:
        try:
            await channels.send_telegram(user.telegram_chat_id, f"{subject}\n\n{text}", url)
            sent += 1
        except Exception:
            logger.exception("notify-telegram-failed", user=str(user.id))

    return sent
