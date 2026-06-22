from __future__ import annotations

from fastapi import APIRouter

from app.auth.dependencies import CurrentUser
from app.schemas.templates import HtmlTemplateOut
from app.services import html_templates as svc

router = APIRouter(prefix="/html-templates", tags=["html-templates"])


@router.get("", response_model=list[HtmlTemplateOut])
async def list_(user: CurrentUser):
    """Die 3 eingebauten HTML-Vorlagen inkl. vollem HTML für die Live-Vorschau."""
    return svc.list_templates()
