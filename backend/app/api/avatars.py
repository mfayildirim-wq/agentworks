from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.auth.dependencies import CurrentUser
from app.schemas.avatars import (
    AvatarGenerateRequest,
    AvatarGenerateResponse,
    AvatarStyleOut,
)
from app.services import avatar_styles
from app.services import avatars as svc

router = APIRouter(prefix="/avatars", tags=["avatars"])


@router.get("/styles", response_model=list[AvatarStyleOut])
async def styles(user: CurrentUser):
    """Auswählbare Avatar-Stile (id, label, group) für das Dropdown."""
    return avatar_styles.list_styles()


@router.post("/generate", response_model=AvatarGenerateResponse)
async def generate(body: AvatarGenerateRequest, user: CurrentUser):
    """Erzeugt aus Name/Beschreibung/Prompt (oder Hinweis) im gewählten Stil ein
    200×200-Avatar-PNG (synchron, ~10–30 s)."""
    try:
        url = await svc.generate_avatar(
            body.name, body.description, body.prompt, body.hint, body.style
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — OpenAI/IO-Fehler → 502
        raise HTTPException(502, f"Avatar-Generierung fehlgeschlagen: {exc}") from exc
    return AvatarGenerateResponse(url=url)
