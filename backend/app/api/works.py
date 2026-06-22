from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.db.session import get_db
from app.schemas.works import WorkCreate, WorkOut
from app.services import works as svc

router = APIRouter(prefix="/works", tags=["works"])


@router.get("", response_model=list[WorkOut])
async def list_(
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    mine: bool = False,
    public_only: bool = False,
):
    return await svc.list_works(db, user, mine=mine, public_only=public_only)


@router.post("", response_model=WorkOut, status_code=201)
async def create(payload: WorkCreate, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    try:
        return await svc.create_work(db, user, payload)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{work_id}", response_model=WorkOut)
async def get_(work_id: UUID, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    out = await svc.get_work(db, work_id, user)
    if out is None:
        raise HTTPException(404, "not found")
    return out


@router.post("/{work_id}/copy", response_model=WorkOut, status_code=201)
async def copy(work_id: UUID, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    out = await svc.copy_work(db, work_id, user)
    if out is None:
        raise HTTPException(404, "not found")
    return out
