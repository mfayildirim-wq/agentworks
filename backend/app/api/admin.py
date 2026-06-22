from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.dependencies import AdminUser, AdminRoleUser    # Systemadmin-only bzw. Admin/Systemadmin
from app.db.session import get_db
from app.schemas.admin import (
    AdminUserOut, GrantCreditIn, PublicationRequestOut, RejectIn, SetRoleIn, SetTopupModeIn,
)
from app.services import roles
from app.services import templates as tpl_svc

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/users", response_model=list[AdminUserOut])
async def list_users(q: str, admin: AdminUser, db: AsyncSession = Depends(get_db)):
    return await roles.search_users(db, q)

@router.put("/users/{user_id}/role", response_model=dict)
async def set_user_role(user_id: UUID, body: SetRoleIn, admin: AdminUser,
                        db: AsyncSession = Depends(get_db)):
    return {"ok": await roles.set_role(db, user_id, body.role)}

@router.put("/users/{user_id}/topup-mode", response_model=dict)
async def set_user_topup_mode(user_id: UUID, body: SetTopupModeIn, admin: AdminUser,
                              db: AsyncSession = Depends(get_db)):
    return {"ok": await roles.set_topup_mode(db, user_id, body.mode)}

@router.post("/users/{user_id}/grant-credit", response_model=dict)
async def grant_credit(user_id: UUID, body: GrantCreditIn, admin: AdminUser,
                       db: AsyncSession = Depends(get_db)):
    """Systemadmin schreibt einem beliebigen Nutzer Guthaben gut (ohne Bezahlung)."""
    from decimal import Decimal

    from app.db.models import User
    from app.services import billing

    target = await db.get(User, user_id)
    if target is None:
        return {"ok": False}
    led = await billing.top_up(db, target, Decimal(str(body.amount_usd)))
    led.description = f"Gutschrift durch Systemadmin ({admin.email})"
    await db.commit()
    return {"ok": True, "balance_usd": float(target.balance_usd or 0)}

@router.get("/publication-requests", response_model=list[PublicationRequestOut])
async def publication_requests(admin: AdminRoleUser, db: AsyncSession = Depends(get_db)):
    return await tpl_svc.list_publication_requests(db)

@router.post("/templates/{template_id}/approve", response_model=dict)
async def approve(template_id: UUID, admin: AdminRoleUser, db: AsyncSession = Depends(get_db)):
    return {"ok": await tpl_svc.approve_publication(db, template_id)}

@router.post("/templates/{template_id}/reject", response_model=dict)
async def reject(template_id: UUID, body: RejectIn, admin: AdminRoleUser, db: AsyncSession = Depends(get_db)):
    return {"ok": await tpl_svc.reject_publication(db, template_id, body.note)}


@router.get("/creator-earnings")
async def creator_earnings(admin: AdminRoleUser, db: AsyncSession = Depends(get_db)):
    """Creator-Anteil (5 %) je Agent-Vorlage: wer wie viel verdient hat."""
    from sqlalchemy import func, select

    from app.db.models import Artifact, Template, User, WalletLedger

    rows = (await db.execute(
        select(
            Template.id, Template.title, User.name,
            func.coalesce(func.sum(WalletLedger.amount_usd), 0).label("total"),
            func.count(WalletLedger.id).label("runs"),
        )
        .join(Artifact, Artifact.id == WalletLedger.artifact_id)
        .join(Template, Template.id == Artifact.template_id)
        .join(User, User.id == Template.owner_id)
        .where(WalletLedger.kind == "royalty")
        .group_by(Template.id, Template.title, User.name)
        .order_by(func.sum(WalletLedger.amount_usd).desc())
    )).all()
    return [
        {"template_id": str(tid), "template_title": title, "creator_name": name,
         "total_usd": float(total), "runs": int(runs)}
        for tid, title, name, total, runs in rows
    ]
