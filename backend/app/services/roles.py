from __future__ import annotations
from uuid import UUID
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.settings import get_settings
from app.db.models import User, Visibility

settings = get_settings()

def is_system_admin(user) -> bool:
    """Systemadmin = erster installierender Nutzer (Flag, höchste Rolle, vormals „GOA").
    Fallback auf die konfigurierte admin_email (Bestandsinstallation/Konfig), falls gesetzt."""
    if not user:
        return False
    if getattr(user, "is_system_admin", False):
        return True
    return bool(settings.admin_email) and user.email == settings.admin_email

# Rückwärtskompatibler Alias.
def is_goa(user) -> bool:
    return is_system_admin(user)

def is_admin(user) -> bool:
    return is_system_admin(user) or getattr(user, "role", "") == "admin"

# Sichtbarkeiten, die NUR der Eigentümer sieht (privat + Entwurf).
OWNER_ONLY = (Visibility.PRIVATE, Visibility.DRAFT)
# Sichtbarkeiten, die normale Nutzer selbst setzen dürfen (privat/Entwurf/Freunde).
# Öffentlich/Per-Link bleibt Admins vorbehalten (normale Nutzer stellen Antrag).
SELF_SETTABLE = (Visibility.PRIVATE, Visibility.DRAFT, Visibility.FRIENDS)


def is_owner_only(visibility) -> bool:
    return visibility in OWNER_ONLY


def effective_visibility(user, requested):
    """Sichtbarkeits-Gating: normale User dürfen private/draft/friends; Admin/Systemadmin
    wie gewünscht (auch public/unlisted). An ALLEN Stellen nutzen, die Template-/Agent-
    Sichtbarkeit aus Nutzer-Eingabe setzen."""
    if is_admin(user) or requested in SELF_SETTABLE:
        return requested
    return Visibility.PRIVATE

async def set_role(db: AsyncSession, target_id: UUID, role: str) -> bool:
    if role not in ("", "admin"):
        return False
    u = await db.get(User, target_id)
    if u is None or u.email == settings.admin_email:   # GOA-Rolle nicht über DB ändern
        return False
    u.role = role
    await db.commit()
    return True

async def set_topup_mode(db: AsyncSession, target_id: UUID, mode: str) -> bool:
    if mode not in ("free", "real"):
        return False
    u = await db.get(User, target_id)
    if u is None or u.email == settings.admin_email:   # GOA unveränderlich
        return False
    u.topup_mode = mode
    await db.commit()
    return True

async def search_users(db: AsyncSession, q: str) -> list[User]:
    q = (q or "").strip()
    if not q:
        return []
    return list((await db.execute(select(User).where(
        or_(User.email == q, User.email.ilike(f"%{q}%"), User.name.ilike(f"%{q}%"))
    ).limit(20))).scalars().all())
