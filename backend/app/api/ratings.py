from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.db.models import Agent, Rating, Visibility
from app.db.session import get_db

router = APIRouter(prefix="/agents/{agent_id}/ratings", tags=["ratings"])


class RatingIn(BaseModel):
    stars: int = Field(ge=1, le=5)
    comment: str = ""


class RatingOut(BaseModel):
    id: UUID
    agent_id: UUID
    user_id: UUID
    stars: int
    comment: str

    model_config = {"from_attributes": True}


@router.post("", response_model=RatingOut, status_code=201)
async def rate(
    agent_id: UUID,
    payload: RatingIn,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    agent = await db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(404, "agent not found")
    if agent.visibility == Visibility.PRIVATE and agent.owner_id != user.id:
        raise HTTPException(403, "cannot rate private agent")
    existing = (
        await db.execute(
            select(Rating).where(Rating.agent_id == agent_id, Rating.user_id == user.id)
        )
    ).scalar_one_or_none()
    if existing:
        existing.stars = payload.stars
        existing.comment = payload.comment
        await db.commit()
        return existing
    rating = Rating(
        agent_id=agent_id, user_id=user.id, stars=payload.stars, comment=payload.comment
    )
    db.add(rating)
    await db.commit()
    await db.refresh(rating)
    return rating


@router.get("", response_model=list[RatingOut])
async def list_(agent_id: UUID, _: CurrentUser, db: AsyncSession = Depends(get_db)):
    stmt = select(Rating).where(Rating.agent_id == agent_id).order_by(Rating.created_at.desc())
    return list((await db.execute(stmt)).scalars().all())
