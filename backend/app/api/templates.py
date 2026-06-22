from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.db.session import get_db
from app.schemas.templates import (
    AgentTemplateCreate,
    AgentTemplateUpdate,
    InstantiateRequest,
    InstantiateResponse,
    PublicTemplateOut,
    TemplateCreate,
    TemplateOut,
    TemplateUpdate,
)
from app.services import templates as svc

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=list[TemplateOut])
async def list_(
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    category: str | None = None,
    mine: bool = False,
):
    return await svc.list_templates(db, user, category=category, mine=mine)


@router.post("", response_model=TemplateOut, status_code=201)
async def create(payload: TemplateCreate, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    return await svc.create_template(db, user, payload)


@router.post("/agent-template", response_model=TemplateOut, status_code=201)
async def create_agent_template(
    payload: AgentTemplateCreate, user: CurrentUser, db: AsyncSession = Depends(get_db)
):
    """Einheitliche „Agent-Vorlage": erzeugt Agent + umhüllendes Template in einem Schritt."""
    try:
        return await svc.create_agent_template(db, user, payload)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.put("/agent-template/{template_id}", response_model=TemplateOut)
async def update_agent_template(
    template_id: UUID,
    payload: AgentTemplateUpdate,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    try:
        out = await svc.update_agent_template(db, template_id, user, payload)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if out is None:
        raise HTTPException(404, "not found or forbidden")
    return out


@router.get("/public", response_model=list[PublicTemplateOut])
async def list_public(
    db: AsyncSession = Depends(get_db),
    category: str | None = None,
    sort: str = "popular",
    q: str = "",
    owner: UUID | None = None,
):
    """Tokenfreie öffentliche Liste für die Startseite (kein Login nötig).
    `owner` filtert auf die Vorlagen eines bestimmten Erstellers (Creator-Profil)."""
    return await svc.list_public_templates(db, category=category, sort=sort, q=q, owner_id=owner)


@router.get("/{template_id}", response_model=TemplateOut)
async def get_(template_id: UUID, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    out = await svc.get_template(db, template_id, user)
    if out is None:
        raise HTTPException(404, "not found")
    return out


@router.patch("/{template_id}", response_model=TemplateOut)
async def update(
    template_id: UUID,
    payload: TemplateUpdate,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    out = await svc.update_template(db, template_id, user, payload)
    if out is None:
        raise HTTPException(404, "not found or forbidden")
    return out


@router.delete("/{template_id}", status_code=204)
async def delete(template_id: UUID, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    if not await svc.delete_template(db, template_id, user):
        raise HTTPException(404, "not found or forbidden")


@router.post("/{template_id}/request-publication", response_model=dict)
async def request_publication(template_id: UUID, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    return {"ok": await svc.request_publication(db, template_id, user)}


@router.post("/{template_id}/instantiate", response_model=InstantiateResponse, status_code=201)
async def instantiate(
    template_id: UUID,
    payload: InstantiateRequest,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    try:
        out = await svc.instantiate(
            db, template_id, user, payload.inputs, output_template=payload.output_template
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    if out is None:
        raise HTTPException(404, "not found")
    return out
