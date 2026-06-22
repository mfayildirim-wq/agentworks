from __future__ import annotations
import json
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.dependencies import CurrentUser
from app.core.settings import get_settings
from app.db.models import Artifact
from app.db.session import get_db
from app.services import artifact_connections as conn_svc
from app.services import google_oauth as go

settings = get_settings()
router = APIRouter(prefix="/oauth/google", tags=["oauth"])

@router.get("/start")
async def start(artifact_id: UUID, user: CurrentUser, kind: str = "google_calendar",
                db: AsyncSession = Depends(get_db)):
    art = await db.get(Artifact, artifact_id)
    if art is None or art.owner_id != user.id:
        raise HTTPException(404, "not found")
    from app.services import connection_registry
    reg = connection_registry.get(kind)
    if reg is None or reg.get("auth") != "oauth":
        raise HTTPException(400, "unbekannter OAuth-Dienst")
    state = go.encode_state(user.id, artifact_id, kind)
    return RedirectResponse(go.build_auth_url(state, go.scopes_for(kind)), status_code=302)

@router.get("/callback")
async def callback(code: str = "", state: str = "", db: AsyncSession = Depends(get_db)):
    data = go.decode_state(state)
    if data is None or not code:
        raise HTTPException(400, "ungültiger state")
    user_id = UUID(data["user_id"]); artifact_id = UUID(data["artifact_id"])
    kind = data.get("kind", "google_calendar")
    try:
        tokens = await go.exchange_code(code)
    except Exception:
        # Code abgelaufen/ungültig/Google-Fehler → saubere 400 ohne Stacktrace/Detail-Leak.
        raise HTTPException(400, "OAuth-Austausch fehlgeschlagen") from None
    blob = {"access_token": tokens.get("access_token"),
            "refresh_token": tokens.get("refresh_token"),
            "expires_at": go._expiry(tokens.get("expires_in", 3600))}
    await conn_svc.upsert_connection(db, artifact_id, user_id,
        kind=kind, config={"connected": True, "scopes": go.scopes_for(kind)},
        secret=json.dumps(blob))
    base = settings.public_base_url.rstrip("/")
    return RedirectResponse(f"{base}/artifacts/{artifact_id}", status_code=302)
