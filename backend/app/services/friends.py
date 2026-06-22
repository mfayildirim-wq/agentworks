from __future__ import annotations
from uuid import UUID
from sqlalchemy import or_, select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Friendship, User


def _pair(a: UUID, b: UUID):
    return or_(
        and_(Friendship.requester_id == a, Friendship.addressee_id == b),
        and_(Friendship.requester_id == b, Friendship.addressee_id == a),
    )

async def are_friends(db: AsyncSession, a_id: UUID, b_id: UUID) -> bool:
    row = (await db.execute(select(Friendship.id).where(_pair(a_id, b_id), Friendship.status == "accepted"))).first()
    return row is not None

async def list_friends(db: AsyncSession, user_id: UUID) -> list[User]:
    return [u for _fid, u in await friends_with_ids(db, user_id)]


async def friends_with_ids(db: AsyncSession, user_id: UUID) -> list[tuple[UUID, User]]:
    """(friendship_id, friend_user) — die friendship_id wird für DELETE /friends/{id}
    gebraucht (nicht die User-id)."""
    rows = (await db.execute(select(Friendship).where(
        or_(Friendship.requester_id == user_id, Friendship.addressee_id == user_id),
        Friendship.status == "accepted"))).scalars().all()
    out: list[tuple[UUID, User]] = []
    for f in rows:
        other_id = f.addressee_id if f.requester_id == user_id else f.requester_id
        u = await db.get(User, other_id)
        if u:
            out.append((f.id, u))
    return out

async def incoming_requests(db: AsyncSession, user_id: UUID) -> list[Friendship]:
    return list((await db.execute(select(Friendship).where(
        Friendship.addressee_id == user_id, Friendship.status == "pending"))).scalars().all())

async def search_users(db: AsyncSession, q: str, exclude_id: UUID) -> list[User]:
    q = (q or "").strip()
    if not q:
        return []
    stmt = select(User).where(
        or_(User.email == q, User.email.ilike(f"%{q}%"), User.name.ilike(f"%{q}%")),
        User.id != exclude_id,
    ).limit(10)
    return list((await db.execute(stmt)).scalars().all())

async def send_request(db: AsyncSession, requester_id: UUID, email_or_name: str) -> Friendship | None:
    target = (await db.execute(select(User).where(
        or_(User.email == email_or_name, User.name == email_or_name)).limit(1))).scalars().first()
    if target is None or target.id == requester_id:
        return None
    existing = (await db.execute(select(Friendship).where(_pair(requester_id, target.id)))).scalars().first()
    if existing is not None:
        # Gegen-Anfrage vorhanden → direkt akzeptieren.
        if existing.status == "pending" and existing.addressee_id == requester_id:
            existing.status = "accepted"
            await db.commit(); await db.refresh(existing)
        return existing
    fr = Friendship(requester_id=requester_id, addressee_id=target.id, status="pending")
    db.add(fr); await db.commit(); await db.refresh(fr)
    return fr

async def accept(db: AsyncSession, friendship_id: UUID, user_id: UUID) -> bool:
    fr = await db.get(Friendship, friendship_id)
    if fr is None or fr.addressee_id != user_id:
        return False
    fr.status = "accepted"; await db.commit()
    return True

async def remove(db: AsyncSession, friendship_id: UUID, user_id: UUID) -> bool:
    fr = await db.get(Friendship, friendship_id)
    if fr is None or user_id not in (fr.requester_id, fr.addressee_id):
        return False
    await db.delete(fr); await db.commit()
    return True
