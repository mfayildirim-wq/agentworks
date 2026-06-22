from __future__ import annotations

from fastapi import APIRouter

from app.auth.dependencies import CurrentUser
from app.services import roles

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
async def me(user: CurrentUser) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "avatar_url": user.avatar_url,
        "role": user.role,
        "is_admin": roles.is_admin(user),
        "is_goa": roles.is_goa(user),
    }
