"""Konkrete Versand-Kanäle. I/O lebt hier; in Tests werden diese Funktionen gemockt.

- E-Mail: stdlib smtplib (Gmail-SMTP), in einen Thread ausgelagert (nicht blockierend).
- Telegram: httpx gegen die Bot-API.
"""

from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage

import httpx

from app.core.logging import logger
from app.core.settings import get_settings

settings = get_settings()


async def send_email(to: str, subject: str, text: str, url: str) -> bool:
    msg = EmailMessage()
    msg["From"] = settings.mail_from or settings.smtp_user
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)

    def _send() -> None:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as s:
            s.starttls()
            if settings.smtp_user:
                s.login(settings.smtp_user, settings.smtp_password)
            s.send_message(msg)

    await asyncio.to_thread(_send)
    return True


async def telegram_api(method: str, payload: dict) -> dict:
    """Ruft eine Telegram-Bot-API-Methode auf (auch vom Poller genutzt)."""
    token = settings.telegram_bot_token
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(f"https://api.telegram.org/bot{token}/{method}", json=payload)
        r.raise_for_status()
        return r.json()


async def send_telegram(chat_id: str, text: str, url: str) -> bool:
    await telegram_api(
        "sendMessage",
        {"chat_id": chat_id, "text": text, "disable_web_page_preview": False},
    )
    return True


def email_configured() -> bool:
    return bool(settings.smtp_host)


def telegram_configured() -> bool:
    return bool(settings.telegram_bot_token)


__all__ = [
    "send_email",
    "send_telegram",
    "telegram_api",
    "email_configured",
    "telegram_configured",
    "logger",
]
