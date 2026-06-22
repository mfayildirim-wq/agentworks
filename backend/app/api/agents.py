from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.db.session import get_db
from app.schemas.agents import AgentCreate, AgentOut, AgentUpdate, AgentWorkRef, ProfileExtract, RatingIn, ReviewOut
from app.services import agents as svc
from app.services import profile_extract as pe

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=list[AgentOut])
async def list_(
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    q: str | None = None,
    skill: str | None = None,
    domain: str | None = None,
    model: str | None = None,
    mine: bool = False,
):
    return await svc.list_agents(
        db, user, query=q, skill=skill, domain=domain, model=model, mine=mine
    )


@router.post("", response_model=AgentOut, status_code=201)
async def create(payload: AgentCreate, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    return await svc.create_agent(db, user, payload)


@router.post("/extract-profile", response_model=ProfileExtract)
async def extract_profile(user: CurrentUser, file: UploadFile = File(...)):
    return await pe.extract_profile(file)


@router.get("/{agent_id}", response_model=AgentOut)
async def get_(agent_id: UUID, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    out = await svc.get_agent(db, agent_id, user)
    if out is None:
        raise HTTPException(404, "not found")
    return out


@router.patch("/{agent_id}", response_model=AgentOut)
async def update(
    agent_id: UUID, payload: AgentUpdate, user: CurrentUser, db: AsyncSession = Depends(get_db)
):
    out = await svc.update_agent(db, agent_id, user, payload)
    if out is None:
        raise HTTPException(404, "not found or forbidden")
    return out


@router.delete("/{agent_id}", status_code=204)
async def delete(agent_id: UUID, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    if not await svc.delete_agent(db, agent_id, user):
        raise HTTPException(404, "not found or forbidden")


@router.get("/{agent_id}/works", response_model=list[AgentWorkRef])
async def agent_works(agent_id: UUID, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    return await svc.list_agent_works(db, agent_id, user)


@router.get("/{agent_id}/reviews", response_model=list[ReviewOut])
async def reviews(agent_id: UUID, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    return await svc.list_reviews(db, agent_id)


@router.post("/{agent_id}/rating", response_model=dict)
async def rate(agent_id: UUID, body: RatingIn, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    r = await svc.rate_agent(db, agent_id, user.id, body.stars, body.comment)
    if r is None:
        raise HTTPException(422, "stars müssen 1–5 sein")
    avg, cnt = (await svc._ratings_map(db, [agent_id])).get(agent_id, (0.0, 0))
    return {"avg_stars": avg, "ratings_count": cnt, "my_stars": body.stars}
