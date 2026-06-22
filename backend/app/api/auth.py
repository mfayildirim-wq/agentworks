"""Auth-Endpoint: tauscht einen frischen Google-id_token gegen ein langlebiges
Backend-Session-Token (Fernet), das danach als Bearer genutzt wird."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import dependencies as deps
from app.auth.session_token import issue_session_token
from app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


class SessionExchangeRequest(BaseModel):
    id_token: str


class SessionExchangeResponse(BaseModel):
    token: str


@router.post("/session", response_model=SessionExchangeResponse)
async def create_session(
    payload: SessionExchangeRequest, db: AsyncSession = Depends(get_db)
) -> SessionExchangeResponse:
    try:
        claims = await deps._verify_google_token(payload.id_token)
    except Exception as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"invalid token: {exc}") from exc

    user = await deps.upsert_user(db, claims)
    token = issue_session_token(
        {
            "sub": user.google_sub,
            "email": user.email,
            "name": user.name,
            "picture": user.avatar_url,
        }
    )
    return SessionExchangeResponse(token=token)
