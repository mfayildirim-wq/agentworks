from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.core.settings import get_settings
from app.db.session import get_db
from app.schemas.profile import ProfileOut, ProfileUpdate, TelegramLinkOut
from app.services import profile as svc
from app.services.notify import telegram_link

router = APIRouter(prefix="/profile", tags=["profile"])
settings = get_settings()


@router.get("", response_model=ProfileOut)
async def get_profile(user: CurrentUser):
    return svc.to_out(user)


@router.put("", response_model=ProfileOut)
async def update_profile(
    payload: ProfileUpdate, user: CurrentUser, db: AsyncSession = Depends(get_db)
):
    return await svc.update(db, user, payload)


@router.post("/telegram/link-token", response_model=TelegramLinkOut)
async def telegram_link_token(user: CurrentUser, db: AsyncSession = Depends(get_db)):
    token = await telegram_link.create_link_token(db, user)
    return TelegramLinkOut(token=token, bot_username=settings.telegram_bot_username)


@router.delete("/telegram", response_model=ProfileOut)
async def telegram_disconnect(user: CurrentUser, db: AsyncSession = Depends(get_db)):
    await telegram_link.disconnect(db, user)
    await db.refresh(user)
    return svc.to_out(user)
