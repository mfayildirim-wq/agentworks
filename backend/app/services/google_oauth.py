from __future__ import annotations
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from uuid import UUID

import httpx
from app.core import crypto
from app.core.settings import get_settings

settings = get_settings()

SCOPE = "https://www.googleapis.com/auth/calendar.events"
_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN = "https://oauth2.googleapis.com/token"

def scopes_for(kind: str) -> str:
    from app.services import connection_registry
    e = connection_registry.get(kind) or {}
    return " ".join(e.get("scopes", []))

def encode_state(user_id: UUID, artifact_id: UUID, kind: str = "google_calendar",
                 ttl_seconds: int = 600) -> str:
    exp = (datetime.now(UTC) + timedelta(seconds=ttl_seconds)).timestamp()
    return crypto.encrypt(json.dumps({"user_id": str(user_id),
                                      "artifact_id": str(artifact_id),
                                      "kind": kind, "exp": exp}))

def decode_state(state: str) -> dict | None:
    try:
        data = json.loads(crypto.decrypt(state))
    except Exception:
        return None
    if float(data.get("exp", 0)) < datetime.now(UTC).timestamp():
        return None
    data.setdefault("kind", "google_calendar")
    return data

def build_auth_url(state: str, scope: str = "") -> str:
    scope = scope or scopes_for("google_calendar")
    q = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_oauth_redirect_uri,
        "response_type": "code",
        "scope": scope,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{_AUTH}?{urlencode(q)}"

async def exchange_code(code: str) -> dict:
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(_TOKEN, data={
            "code": code, "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": settings.google_oauth_redirect_uri,
            "grant_type": "authorization_code"})
        r.raise_for_status()
        return r.json()  # access_token, refresh_token, expires_in, ...

async def refresh_access_token(refresh_token: str) -> dict:
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(_TOKEN, data={
            "refresh_token": refresh_token, "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret, "grant_type": "refresh_token"})
        r.raise_for_status()
        return r.json()  # access_token, expires_in (kein neuer refresh_token)

def _expiry(expires_in: int) -> float:
    return (datetime.now(UTC) + timedelta(seconds=int(expires_in) - 60)).timestamp()

async def get_valid_access_token(db, artifact_id: UUID, owner_id: UUID,
                                 kind: str = "google_calendar") -> str | None:
    """Lädt die Verbindung der Instanz für `kind`; refresht den Access-Token bei
    Ablauf und persistiert ihn. None, wenn nicht verbunden."""
    from app.services import artifact_connections as conn_svc
    conn = await conn_svc.get_connection(db, artifact_id, owner_id, kind)
    if conn is None or not conn.secret_encrypted:
        return None
    try:
        tok = json.loads(crypto.decrypt(conn.secret_encrypted))
    except Exception:
        return None
    if float(tok.get("expires_at", 0)) > datetime.now(UTC).timestamp() and tok.get("access_token"):
        return tok["access_token"]
    rt = tok.get("refresh_token")
    if not rt:
        return None
    fresh = await refresh_access_token(rt)
    tok["access_token"] = fresh["access_token"]
    tok["expires_at"] = _expiry(fresh.get("expires_in", 3600))
    await conn_svc.upsert_connection(db, artifact_id, owner_id,
        kind=kind, config={}, secret=json.dumps(tok))
    return tok["access_token"]
