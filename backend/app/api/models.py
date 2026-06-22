from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.db.session import get_db
from app.services import models as svc

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=list[dict])
async def list_models(user: CurrentUser, db: AsyncSession = Depends(get_db)):
    return await svc.list_models(db)
