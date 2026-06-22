from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.core.settings import get_settings
from app.db.models import Artifact, WalletLedger
from app.db.session import get_db
from app.schemas.billing import (
    ConfirmRequest,
    InstanceUsageOut,
    LedgerItem,
    TopUpOut,
    TopUpRequest,
    WalletOut,
)
from app.services import billing, stripe_pay

settings = get_settings()

router = APIRouter(prefix="/wallet", tags=["wallet"])


@router.get("", response_model=WalletOut)
async def get_wallet(user: CurrentUser, db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(WalletLedger)
        .where(WalletLedger.user_id == user.id)
        .order_by(WalletLedger.created_at.desc())
        .limit(100)
    )).scalars().all()
    items = [LedgerItem.model_validate(r) for r in rows]
    ids = {r.artifact_id for r in rows if r.artifact_id is not None}
    titles: dict = {}
    if ids:
        res = await db.execute(select(Artifact.id, Artifact.title).where(Artifact.id.in_(ids)))
        titles = {i: t for i, t in res.all()}
    for it, r in zip(items, rows):
        if r.artifact_id is not None:
            it.app_name = titles.get(r.artifact_id)
    return WalletOut(balance_usd=user.balance_usd or 0, ledger=items,
                     topup_mode=billing.effective_topup_mode(user))


@router.get("/by-instance", response_model=list[InstanceUsageOut])
async def by_instance(user: CurrentUser, db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(
            WalletLedger.artifact_id,
            func.sum(-WalletLedger.amount_usd).label("total"),
            func.count().label("runs"),
            func.max(WalletLedger.created_at).label("last_at"),
        )
        .where(
            WalletLedger.user_id == user.id,
            WalletLedger.kind == "charge",
            WalletLedger.artifact_id.is_not(None),
        )
        .group_by(WalletLedger.artifact_id)
        .order_by(func.sum(-WalletLedger.amount_usd).desc())
        .limit(100)
    )).all()
    out: list[InstanceUsageOut] = []
    for aid, total, runs, last_at in rows:
        art = await db.get(Artifact, aid)
        if art is None:
            continue
        out.append(InstanceUsageOut(
            artifact_id=aid, title=art.title or "Instanz", icon=None,
            total_usd=total or 0, runs=runs, last_at=last_at))
    return out


@router.post("/topup", response_model=TopUpOut)
async def topup(body: TopUpRequest, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    mode = billing.effective_topup_mode(user)
    if mode == "free":
        await billing.top_up(db, user, body.amount_usd)
        await db.commit()
        await db.refresh(user)
        return TopUpOut(mode="free", checkout_url=None, wallet=await get_wallet(user, db))
    if not stripe_pay.is_configured():
        raise HTTPException(status_code=503, detail="Bezahlung ist noch nicht eingerichtet.")
    base = settings.public_base_url.rstrip("/")
    url = stripe_pay.create_checkout_session(
        body.amount_usd, user_id=user.id,
        success_url=f"{base}/profile?topup=success&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base}/profile?topup=cancel")
    if not url:
        raise HTTPException(status_code=503, detail="Bezahlung ist noch nicht eingerichtet.")
    return TopUpOut(mode="real", checkout_url=url, wallet=None)


@router.post("/stripe/confirm", response_model=WalletOut)
async def stripe_confirm(body: ConfirmRequest, user: CurrentUser,
                         db: AsyncSession = Depends(get_db)):
    paid, amount, ref = stripe_pay.retrieve_paid_amount(body.session_id)
    already = (await db.execute(
        select(WalletLedger.id).where(WalletLedger.external_ref == body.session_id)
    )).first()
    if paid and ref == str(user.id) and amount > 0 and already is None:
        try:
            await billing.top_up(db, user, amount, external_ref=body.session_id)
            await db.commit()
            await db.refresh(user)
        except IntegrityError:
            # Gleichzeitiger Confirm-Call hat dieselbe session_id schon gebucht
            # (Unique-Index auf external_ref) → still als „bereits gutgeschrieben" behandeln.
            await db.rollback()
            await db.refresh(user)
    return await get_wallet(user, db)
