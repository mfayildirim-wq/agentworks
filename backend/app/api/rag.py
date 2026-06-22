from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.db.models import Agent, RagDocument
from app.db.session import get_db
from app.services import rag

router = APIRouter(prefix="/agents/{agent_id}/rag", tags=["rag"])


class DocumentIn(BaseModel):
    title: str
    text: str


class DocumentOut(BaseModel):
    id: UUID
    title: str
    chunk: str

    model_config = {"from_attributes": True}


@router.post("/documents")
async def add_document(
    agent_id: UUID,
    payload: DocumentIn,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    agent = await db.get(Agent, agent_id)
    if agent is None or agent.owner_id != user.id:
        raise HTTPException(404, "not found or forbidden")
    n = await rag.ingest(db, agent_id, payload.title, payload.text)
    return {"chunks": n}


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(
    agent_id: UUID, user: CurrentUser, db: AsyncSession = Depends(get_db)
):
    agent = await db.get(Agent, agent_id)
    if agent is None or agent.owner_id != user.id:
        raise HTTPException(404, "not found or forbidden")
    stmt = select(RagDocument).where(RagDocument.agent_id == agent_id).limit(200)
    return list((await db.execute(stmt)).scalars().all())
