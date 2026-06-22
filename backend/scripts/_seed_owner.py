"""Shared helper for seed scripts: resolve the owner of seeded public templates.

The owner is the *system admin* of this installation: the user with
``User.is_system_admin == True``. The very first user who logs in becomes the
system admin automatically. As a fallback (e.g. the flag was never set) the
oldest user is used.

No hard-coded e-mail address — the seed scripts work on any fresh installation.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


async def resolve_seed_owner(db: AsyncSession) -> User:
    """Return the system admin (or oldest user) that owns the seeded templates.

    Raises ``SystemExit`` with a friendly message if no user exists yet.
    """
    owner = (
        await db.execute(select(User).where(User.is_system_admin.is_(True)))
    ).scalars().first()
    if owner is None:
        owner = (
            await db.execute(select(User).order_by(User.created_at).limit(1))
        ).scalars().first()
    if owner is None:
        raise SystemExit(
            "No user found. Please log in once first (the first user becomes the "
            "system admin), then run the seed again."
        )
    return owner
