from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.dependencies import CurrentUser
from app.db.session import get_db
from app.schemas.friends import FriendOut, FriendRequestIn, FriendRequestOut, UserSearchOut
from app.services import friends

router = APIRouter(prefix="/friends", tags=["friends"])

@router.get("", response_model=list[FriendOut])
async def my_friends(user: CurrentUser, db: AsyncSession = Depends(get_db)):
    # id = friendship_id (für DELETE /friends/{id}), nicht die User-id.
    return [
        FriendOut(id=fid, name=u.name, email=u.email, avatar_url=u.avatar_url)
        for fid, u in await friends.friends_with_ids(db, user.id)
    ]

@router.get("/requests", response_model=list[FriendRequestOut])
async def my_requests(user: CurrentUser, db: AsyncSession = Depends(get_db)):
    out = []
    for f in await friends.incoming_requests(db, user.id):
        from app.db.models import User
        u = await db.get(User, f.requester_id)
        out.append(FriendRequestOut(id=f.id, requester_id=f.requester_id,
                                    name=u.name if u else "", avatar_url=u.avatar_url if u else None))
    return out

@router.get("/search", response_model=list[UserSearchOut])
async def search(q: str, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    return await friends.search_users(db, q, exclude_id=user.id)

@router.post("/request", response_model=dict)
async def request(body: FriendRequestIn, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    fr = await friends.send_request(db, user.id, body.email_or_name)
    return {"ok": fr is not None, "status": fr.status if fr else None}

@router.post("/{friendship_id}/accept", response_model=dict)
async def accept(friendship_id: UUID, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    return {"ok": await friends.accept(db, friendship_id, user.id)}

@router.delete("/{friendship_id}", response_model=dict)
async def remove(friendship_id: UUID, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    return {"ok": await friends.remove(db, friendship_id, user.id)}
