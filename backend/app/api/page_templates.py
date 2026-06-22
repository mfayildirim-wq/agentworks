from __future__ import annotations

from fastapi import APIRouter

from app.auth.dependencies import CurrentUser
from app.services import page_templates as svc

router = APIRouter(prefix="/page-templates", tags=["page-templates"])


@router.get("")
async def list_(user: CurrentUser):
    """Die 'fertigen' Seiten-Vorlagen (prepared) inkl. Platzhalter für die Instanz-Auswahl."""
    return svc.list_all()
