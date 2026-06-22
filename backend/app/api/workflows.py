"""Workflow-Editor: lädt/speichert Graph in `works.workflow_graph` (JSONB).

Format:
    {
      "nodes": [{"id": "<work_agent_id>", "x": 120, "y": 80}, ...],
      "edges": [{"source": "<from_agent_id>", "target": "<to_agent_id>"}, ...]
    }

Beim Speichern werden Edges zusätzlich auf `work_agents.handoff_targets` projiziert,
damit die GraphFlow-Runtime sie direkt nutzen kann.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import CurrentUser
from app.db.models import RunMode, Work, WorkAgent
from app.db.session import get_db

router = APIRouter(prefix="/works/{work_id}/workflow", tags=["workflows"])


class GraphNode(BaseModel):
    id: str  # agent_id as string
    x: float = 0
    y: float = 0


class GraphEdge(BaseModel):
    source: str
    target: str


class GraphPayload(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


@router.get("", response_model=GraphPayload)
async def get_(work_id: UUID, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    work = await db.get(Work, work_id)
    if work is None or work.owner_id != user.id:
        raise HTTPException(404, "not found")
    g = work.workflow_graph or {"nodes": [], "edges": []}
    return GraphPayload(**g)


@router.put("", response_model=GraphPayload)
async def put_(
    work_id: UUID,
    payload: GraphPayload,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    work = await db.get(Work, work_id)
    if work is None or work.owner_id != user.id:
        raise HTTPException(404, "not found")
    work.workflow_graph = payload.model_dump()
    work.mode = RunMode.GRAPH

    stmt = (
        select(Work)
        .options(selectinload(Work.work_agents))
        .where(Work.id == work_id)
    )
    work_full = (await db.execute(stmt)).scalar_one()
    edges_by_source: dict[str, list[str]] = {}
    for e in payload.edges:
        edges_by_source.setdefault(e.source, []).append(e.target)
    for wa in work_full.work_agents:
        wa.handoff_targets = edges_by_source.get(str(wa.agent_id), [])
    await db.commit()
    return payload
