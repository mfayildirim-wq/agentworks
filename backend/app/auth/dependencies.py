"""Auth-Middleware: validiert Google ID-Token aus `Authorization: Bearer …`."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session_token import read_session_token
from app.core.settings import get_settings
from app.db.models import User
from app.db.session import get_db

settings = get_settings()


async def _verify_google_token(token: str) -> dict:
    from google.auth.transport import requests as g_requests
    from google.oauth2 import id_token

    return id_token.verify_oauth2_token(
        token, g_requests.Request(), settings.google_client_id or None
    )


async def upsert_user(db: AsyncSession, claims: dict) -> User:
    """Lädt/legt den User anhand der Token-Claims (sub/email/name/picture) an."""
    sub = claims.get("sub")
    email = claims.get("email")
    if not sub or not email:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token missing sub/email")

    result = await db.execute(select(User).where(User.google_sub == sub))
    user = result.scalar_one_or_none()
    if user is None:
        from decimal import Decimal

        from sqlalchemy import func

        from app.db.models import WalletLedger

        # Erster Nutzer der Installation = Systemadmin.
        is_first = (await db.execute(select(func.count(User.id)))).scalar_one() == 0
        user = User(
            google_sub=sub,
            email=email,
            name=claims.get("name", email),
            avatar_url=claims.get("picture"),
            is_system_admin=is_first,
            topup_mode="real",                 # weiteres Guthaben per Bezahlung/Admin-Gutschrift
            balance_usd=Decimal("2.00"),        # Willkommens-Guthaben
        )
        db.add(user)
        await db.flush()
        db.add(WalletLedger(user_id=user.id, kind="topup", amount_usd=Decimal("2.00"),
                            description="Willkommens-Guthaben"))
        await db.commit()
        await db.refresh(user)
    return user


async def get_current_user(
    request: Request, db: Annotated[AsyncSession, Depends(get_db)]
) -> User:
    if settings.auth_disabled_for_tests:
        return await _get_or_create_test_user(db)

    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    token = header.split(" ", 1)[1]

    # 1) Bevorzugt: langlebiges Backend-Session-Token (kein Netz-Call, kein 1h-Ablauf).
    claims = read_session_token(token)
    if claims is None:
        # 2) Fallback: frischer Google-id_token (z.B. beim ersten Tausch-Call).
        try:
            claims = await _verify_google_token(token)
        except Exception as exc:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"invalid token: {exc}") from exc

    return await upsert_user(db, claims)


async def _get_or_create_test_user(db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.google_sub == "test-user"))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(google_sub="test-user", email="test@local", name="Test User")
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user


async def get_current_user_optional(
    request: Request, db: Annotated[AsyncSession, Depends(get_db)]
) -> User | None:
    if settings.auth_disabled_for_tests:
        return await _get_or_create_test_user(db)
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    token = header.split(" ", 1)[1]
    claims = read_session_token(token)
    if claims is None:
        try:
            claims = await _verify_google_token(token)
        except Exception:
            return None
    return await upsert_user(db, claims)


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_current_user_optional)]


async def get_admin_user(user: CurrentUser) -> User:
    from app.services import roles
    if not roles.is_system_admin(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "system admin only")
    return user


AdminUser = Annotated[User, Depends(get_admin_user)]


async def get_admin_or_goa(user: CurrentUser) -> User:
    from app.services import roles
    if not roles.is_admin(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admin only")
    return user

AdminRoleUser = Annotated[User, Depends(get_admin_or_goa)]
