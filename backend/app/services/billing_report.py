"""Abrechnungs-Auswertung über das WalletLedger (GOA-Reporting).

Begriffe:
- *Einkauf* (``einkauf_usd``)  = was der Provider real gekostet hat (``provider_cost_usd``).
- *Verkauf* (``verkauf_usd``)  = was dem Nutzer berechnet wurde. Bei ``kind='charge'`` ist
  ``amount_usd`` negativ (Abbuchung) → Verkauf = ``-amount_usd``.
- *Gewinn*  (``gewinn_usd``)   = Verkauf − Einkauf.
- *Topups*                     = aufgeladenes Guthaben (``kind='topup'``).
- *Saldo*                      = Summe aller signierten ``amount_usd`` (Topups − Charges).
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, WalletLedger

_ZERO = Decimal("0")


def _d(v) -> Decimal:
    return v if v is not None else _ZERO


def _i(v) -> int:
    return int(v) if v is not None else 0


async def model_summary(db: AsyncSession) -> dict:
    """Aggregiert ``kind='charge'`` je Modell + eine Gesamtzeile.

    Rückgabe ``{"models": [row, ...], "total": row}`` mit row-Feldern
    ``model, runs, tokens_in, tokens_out, einkauf_usd, verkauf_usd, gewinn_usd``.
    """
    stmt = (
        select(
            WalletLedger.model.label("model"),
            func.count().label("runs"),
            func.coalesce(func.sum(WalletLedger.tokens_in), 0).label("tokens_in"),
            func.coalesce(func.sum(WalletLedger.tokens_out), 0).label("tokens_out"),
            func.coalesce(func.sum(WalletLedger.provider_cost_usd), 0).label("einkauf"),
            func.coalesce(func.sum(-WalletLedger.amount_usd), 0).label("verkauf"),
        )
        .where(WalletLedger.kind == "charge")
        .group_by(WalletLedger.model)
        .order_by(WalletLedger.model)
    )
    rows = (await db.execute(stmt)).all()

    models: list[dict] = []
    t_runs = 0
    t_tin = 0
    t_tout = 0
    t_ein = _ZERO
    t_ver = _ZERO
    for r in rows:
        einkauf = _d(r.einkauf)
        verkauf = _d(r.verkauf)
        models.append({
            "model": r.model,
            "runs": _i(r.runs),
            "tokens_in": _i(r.tokens_in),
            "tokens_out": _i(r.tokens_out),
            "einkauf_usd": einkauf,
            "verkauf_usd": verkauf,
            "gewinn_usd": verkauf - einkauf,
        })
        t_runs += _i(r.runs)
        t_tin += _i(r.tokens_in)
        t_tout += _i(r.tokens_out)
        t_ein += einkauf
        t_ver += verkauf

    total = {
        "model": "GESAMT",
        "runs": t_runs,
        "tokens_in": t_tin,
        "tokens_out": t_tout,
        "einkauf_usd": t_ein,
        "verkauf_usd": t_ver,
        "gewinn_usd": t_ver - t_ein,
    }
    return {"models": models, "total": total}


async def user_consumption(db: AsyncSession, user_id: UUID) -> dict:
    """Kennzahlen eines Nutzers über sein gesamtes Ledger."""
    charge = (await db.execute(
        select(
            func.coalesce(func.sum(WalletLedger.tokens_in), 0),
            func.coalesce(func.sum(WalletLedger.tokens_out), 0),
            func.coalesce(func.sum(WalletLedger.provider_cost_usd), 0),
            func.coalesce(func.sum(-WalletLedger.amount_usd), 0),
            func.count(),
        ).where(WalletLedger.user_id == user_id, WalletLedger.kind == "charge")
    )).one()
    topups = (await db.execute(
        select(func.coalesce(func.sum(WalletLedger.amount_usd), 0)).where(
            WalletLedger.user_id == user_id, WalletLedger.kind == "topup"
        )
    )).scalar_one()
    saldo = (await db.execute(
        select(func.coalesce(func.sum(WalletLedger.amount_usd), 0)).where(
            WalletLedger.user_id == user_id
        )
    )).scalar_one()

    einkauf = _d(charge[2])
    verkauf = _d(charge[3])
    return {
        "user_id": str(user_id),
        "tokens_in": _i(charge[0]),
        "tokens_out": _i(charge[1]),
        "einkauf_usd": einkauf,
        "verkauf_usd": verkauf,
        "gewinn_usd": verkauf - einkauf,
        "runs": _i(charge[4]),
        "topups_usd": _d(topups),
        "saldo_usd": _d(saldo),
    }


async def search_users(db: AsyncSession, q: str, limit: int = 20) -> list[dict]:
    """Nutzer per email/name (ILIKE) suchen; je Treffer schlanke Kennzahlen."""
    q = (q or "").strip()
    if not q:
        return []
    users = list((await db.execute(
        select(User)
        .where(or_(User.email.ilike(f"%{q}%"), User.name.ilike(f"%{q}%")))
        .order_by(User.email)
        .limit(limit)
    )).scalars().all())

    out: list[dict] = []
    for u in users:
        c = await user_consumption(db, u.id)
        out.append({
            "user_id": str(u.id),
            "email": u.email,
            "name": u.name,
            "saldo_usd": c["saldo_usd"],
            "verkauf_usd": c["verkauf_usd"],
        })
    return out
