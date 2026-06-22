from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.db.session import get_db
from app.services import media as svc

router = APIRouter(prefix="/media", tags=["media"])


@router.post("/upload")
async def upload(user: CurrentUser, file: UploadFile = File(...)) -> dict:
    url = await svc.save_upload(file, kind="avatars")
    return {"url": url}


@router.get("/free-avatars")
async def free_avatars(user: CurrentUser, db: AsyncSession = Depends(get_db)) -> dict:
    """Nicht zugeordnete Avatar-Bilder im Ordner — für die manuelle Zuordnung."""
    return {"avatars": await svc.list_free_avatars(db)}
