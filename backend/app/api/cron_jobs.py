from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.db.models import CronJob, Work
from app.db.session import get_db

router = APIRouter(prefix="/cron-jobs", tags=["cron"])


class CronCreate(BaseModel):
    work_id: UUID
    cron_expr: str = Field(min_length=9, max_length=120)
    enabled: bool = True
    max_cost_usd: float = 1.0


class CronOut(BaseModel):
    id: UUID
    work_id: UUID
    cron_expr: str
    enabled: bool
    max_cost_usd: float

    model_config = {"from_attributes": True}


@router.get("", response_model=list[CronOut])
async def list_(user: CurrentUser, db: AsyncSession = Depends(get_db)):
    stmt = select(CronJob).where(CronJob.owner_id == user.id)
    return list((await db.execute(stmt)).scalars().all())


@router.post("", response_model=CronOut, status_code=201)
async def create(payload: CronCreate, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    from croniter import croniter

    if not croniter.is_valid(payload.cron_expr):
        raise HTTPException(400, "invalid cron expression")
    work = await db.get(Work, payload.work_id)
    if work is None or work.owner_id != user.id:
        raise HTTPException(404, "work not found")
    job = CronJob(
        owner_id=user.id,
        work_id=payload.work_id,
        cron_expr=payload.cron_expr,
        enabled=payload.enabled,
        max_cost_usd=payload.max_cost_usd,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


@router.delete("/{job_id}", status_code=204)
async def delete(job_id: UUID, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    job = await db.get(CronJob, job_id)
    if job is None or job.owner_id != user.id:
        raise HTTPException(404, "not found")
    await db.delete(job)
    await db.commit()
