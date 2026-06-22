from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.db.session import get_db
from app.schemas.works import MessageOut, RunOut
from app.services import event_bus, runs as run_svc, works as work_svc

router = APIRouter(prefix="/works/{work_id}/runs", tags=["runs"])


@router.post("", response_model=RunOut, status_code=201)
async def start_run(work_id: UUID, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    work = await work_svc.can_access_work(db, work_id, user)
    if work is None:
        raise HTTPException(404, "work not found")
    run = await run_svc.create_run(db, work_id, user.id)
    if run is None:
        raise HTTPException(404, "work not found")
    from app.workers import execute_run

    execute_run.send(str(run.id))
    return run


@router.get("/{run_id}", response_model=RunOut)
async def get_run(
    work_id: UUID, run_id: UUID, user: CurrentUser, db: AsyncSession = Depends(get_db)
):
    work = await work_svc.can_access_work(db, work_id, user)
    if work is None:
        raise HTTPException(404, "work not found")
    from app.db.models import WorkRun

    run = await db.get(WorkRun, run_id)
    if run is None or run.work_id != work_id:
        raise HTTPException(404, "run not found")
    return run


@router.get("/{run_id}/messages", response_model=list[MessageOut])
async def get_messages(
    work_id: UUID, run_id: UUID, user: CurrentUser, db: AsyncSession = Depends(get_db)
):
    work = await work_svc.can_access_work(db, work_id, user)
    if work is None:
        raise HTTPException(404, "work not found")
    return await run_svc.list_messages(db, run_id)


@router.get("/{run_id}/stream")
async def stream(
    work_id: UUID, run_id: UUID, user: CurrentUser, db: AsyncSession = Depends(get_db)
):
    work = await work_svc.can_access_work(db, work_id, user)
    if work is None:
        raise HTTPException(404, "work not found")
    return StreamingResponse(
        event_bus.subscribe_stream(run_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
