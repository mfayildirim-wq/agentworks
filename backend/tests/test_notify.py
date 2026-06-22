"""Tests für Benachrichtigungen: Nachrichtentexte + Kanal-Auswahl im Dispatcher."""

from __future__ import annotations

import pytest

from app.db.models import User
from app.services.notify import dispatch, messages


def _user(**kw) -> User:
    u = User(google_sub="s", email="u@ex.de", name="U")
    for k, v in kw.items():
        setattr(u, k, v)
    return u


def test_subject_and_body_contain_title_version_and_link():
    subject = messages.update_subject("Reiseplan London", 3)
    body = messages.update_body("Reiseplan London", 3, "https://x.de/artifacts/abc")
    assert "Reiseplan London" in subject
    assert "3" in subject
    assert "Reiseplan London" in body
    assert "https://x.de/artifacts/abc" in body


@pytest.mark.asyncio
async def test_dispatch_uses_email_and_telegram_when_enabled(monkeypatch):
    calls: list = []

    async def fake_email(to, subject, text, url):
        calls.append(("email", to))
        return True

    async def fake_tg(chat_id, text, url):
        calls.append(("tg", chat_id))
        return True

    monkeypatch.setattr(dispatch.channels, "send_email", fake_email)
    monkeypatch.setattr(dispatch.channels, "send_telegram", fake_tg)
    monkeypatch.setattr(dispatch.settings, "smtp_host", "smtp.gmail.com")
    monkeypatch.setattr(dispatch.settings, "telegram_bot_token", "tok")

    u = _user(notify_email=True, notify_telegram=True, telegram_chat_id="123")
    await dispatch.notify_user(u, "s", "t", "https://x")
    assert ("email", "u@ex.de") in calls
    assert ("tg", "123") in calls


@pytest.mark.asyncio
async def test_dispatch_skips_telegram_without_chat_id(monkeypatch):
    calls: list = []

    async def fake_email(to, subject, text, url):
        calls.append("email")
        return True

    async def fake_tg(chat_id, text, url):
        calls.append("tg")
        return True

    monkeypatch.setattr(dispatch.channels, "send_email", fake_email)
    monkeypatch.setattr(dispatch.channels, "send_telegram", fake_tg)
    monkeypatch.setattr(dispatch.settings, "smtp_host", "smtp.gmail.com")
    monkeypatch.setattr(dispatch.settings, "telegram_bot_token", "tok")

    u = _user(notify_email=True, notify_telegram=True, telegram_chat_id=None)
    await dispatch.notify_user(u, "s", "t", "https://x")
    assert calls == ["email"]  # ohne chat_id kein Telegram


@pytest.mark.asyncio
async def test_dispatch_respects_prefs_and_missing_settings(monkeypatch):
    calls: list = []

    async def fake_email(to, subject, text, url):
        calls.append("email")
        return True

    async def fake_tg(chat_id, text, url):
        calls.append("tg")
        return True

    monkeypatch.setattr(dispatch.channels, "send_email", fake_email)
    monkeypatch.setattr(dispatch.channels, "send_telegram", fake_tg)
    # E-Mail-Pref aus + kein SMTP-Host; Telegram-Pref aus → gar nichts.
    monkeypatch.setattr(dispatch.settings, "smtp_host", "")
    monkeypatch.setattr(dispatch.settings, "telegram_bot_token", "tok")

    u = _user(notify_email=False, notify_telegram=False, telegram_chat_id="123")
    await dispatch.notify_user(u, "s", "t", "https://x")
    assert calls == []


@pytest.mark.asyncio
async def test_dispatch_is_best_effort_when_a_channel_raises(monkeypatch):
    calls: list = []

    async def boom_email(to, subject, text, url):
        raise RuntimeError("smtp down")

    async def fake_tg(chat_id, text, url):
        calls.append("tg")
        return True

    monkeypatch.setattr(dispatch.channels, "send_email", boom_email)
    monkeypatch.setattr(dispatch.channels, "send_telegram", fake_tg)
    monkeypatch.setattr(dispatch.settings, "smtp_host", "smtp.gmail.com")
    monkeypatch.setattr(dispatch.settings, "telegram_bot_token", "tok")

    u = _user(notify_email=True, notify_telegram=True, telegram_chat_id="123")
    # darf nicht werfen; Telegram trotzdem versendet
    await dispatch.notify_user(u, "s", "t", "https://x")
    assert calls == ["tg"]


def test_update_chat_text():
    from app.services.notify import messages

    out = messages.update_chat_text("Reiseplan", 3, "https://x.de/artifacts/abc")
    assert "Reiseplan" in out and "3" in out and "https://x.de/artifacts/abc" in out


def test_reminder_subject():
    from app.services.notify.messages import reminder_subject
    assert reminder_subject("Timer Agent") == "🔔 Timer Agent"


def test_reminder_chat_text_strips_fences_and_whitespace():
    from app.services.notify.messages import reminder_chat_text
    assert reminder_chat_text("  Hallo 👋  ") == "Hallo 👋"
    assert reminder_chat_text("```\nHallo\n```") == "Hallo"
    assert reminder_chat_text("") == ""
    assert reminder_chat_text(None) == ""
