"""Langlebiges Backend-Session-Token.

Nach **einmaliger** Google-Prüfung stellt das Backend ein eigenes Token aus, das
der Client als Bearer mitschickt — entkoppelt von der 1-Stunden-Lebensdauer des
Google-`id_token`. Umgesetzt als Fernet-verschlüsseltes JSON (authentisiert +
mit Zeitstempel), Schlüssel = `AGENT_SECRET_KEY`. Keine neue Abhängigkeit nötig.
"""

from __future__ import annotations

import json
import time
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.settings import get_settings

# 30 Tage; danach muss der Client einmal neu einloggen.
SESSION_TTL_SECONDS = 30 * 24 * 3600


@lru_cache
def _fernet() -> Fernet:
    key = get_settings().agent_secret_key
    if not key:
        raise RuntimeError("AGENT_SECRET_KEY ist nicht gesetzt (Fernet-Key erforderlich)")
    return Fernet(key.encode())


def issue_session_token(claims: dict, *, now: int | None = None) -> str:
    """Stellt ein Session-Token aus den Claims (sub/email/name/picture) aus."""
    data = json.dumps(claims, separators=(",", ":")).encode()
    ts = int(now if now is not None else time.time())
    return _fernet().encrypt_at_time(data, ts).decode()


def read_session_token(
    token: str, *, max_age_seconds: int = SESSION_TTL_SECONDS, now: int | None = None
) -> dict | None:
    """Liest/validiert ein Session-Token. Gibt Claims zurück oder None (ungültig/abgelaufen)."""
    ts = int(now if now is not None else time.time())
    try:
        raw = _fernet().decrypt_at_time(token.encode(), max_age_seconds, ts)
    except (InvalidToken, ValueError, TypeError):
        return None
    try:
        claims = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return claims if isinstance(claims, dict) else None
