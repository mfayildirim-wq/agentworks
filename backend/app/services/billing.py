"""Wallet-Buchungen & Loop-Abrechnung (rein, DB-only). Geld als Decimal."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Artifact, ArtifactVersion, Template, User, WalletLedger, WorkRun
from app.services import model_pricing, roles

# Gesamtaufschlag auf die LLM-Kosten = 30 %: 25 % Portal + 5 % Creator (Template-Ersteller).
MARGIN = Decimal("1.30")
CREATOR_SHARE = Decimal("0.05")
IMAGE_PRICE_USD = Decimal("0.02")   # Endpreis je erzeugtem Bild (gpt-image-1)


async def _credit_creator_royalty(
    db: AsyncSession, *, artifact_id: uuid.UUID | None, owner_id: uuid.UUID | None,
    cost: Decimal, model: str,
) -> WalletLedger | None:
    """Schreibt dem Template-Ersteller 5 % der LLM-Kosten gut (aus der Portal-Marge).
    Nur für Template-Instanzen und NICHT, wenn der Ersteller die eigene Vorlage nutzt."""
    if artifact_id is None or owner_id is None or cost <= 0:
        return None
    art = await db.get(Artifact, artifact_id)
    if art is None or art.template_id is None:
        return None
    tpl = await db.get(Template, art.template_id)
    if tpl is None or tpl.owner_id is None or tpl.owner_id == owner_id:
        return None
    royalty = (cost * CREATOR_SHARE).quantize(Decimal("0.000001"))
    if royalty <= 0:
        return None
    creator = await db.get(User, tpl.owner_id)
    if creator is None:
        return None
    creator.balance_usd = (creator.balance_usd or Decimal("0")) + royalty
    led = WalletLedger(
        user_id=tpl.owner_id, kind="royalty", amount_usd=royalty, artifact_id=artifact_id,
        run_id=None, model=model, provider_cost_usd=cost, margin=CREATOR_SHARE,
        description=f"Creator-Anteil {tpl.title}",
    )
    db.add(led)
    return led


def effective_topup_mode(user) -> str:
    """Effektiver Aufladeweg: 'free' (Attrappe) oder 'real' (Stripe). Kein Admin-Sonderrecht
    mehr — stattdessen kann der Systemadmin gezielt Guthaben gutschreiben (Admin-Tab)."""
    return "real" if getattr(user, "topup_mode", "free") == "real" else "free"


def provider_cost(pin: Decimal, pout: Decimal, tin: int, tout: int) -> Decimal:
    return (Decimal(tin) / 1_000_000) * pin + (Decimal(tout) / 1_000_000) * pout


async def top_up(db: AsyncSession, user: User, amount_usd: Decimal,
                 *, external_ref: str | None = None) -> WalletLedger:
    user.balance_usd = (user.balance_usd or Decimal("0")) + amount_usd
    led = WalletLedger(user_id=user.id, kind="topup", amount_usd=amount_usd,
                       description="Guthaben aufgeladen", external_ref=external_ref)
    db.add(led)
    return led


async def remaining_run_budget(db: AsyncSession, user: User) -> Decimal:
    bal = user.balance_usd or Decimal("0")
    return (bal / MARGIN) if bal > 0 else Decimal("0")


async def instance_completed_loops(db: AsyncSession, artifact_id: uuid.UUID) -> int:
    """Zahl der bisher erzeugten Versionen (= abgeschlossene Loops) dieser Instanz.

    Eine Instanz spannt mehrere Works/Runs (jedes Update legt ein neues Work an),
    darum wird der Gratis-Lauf pro **Instanz** über die Artefakt-Versionen gezählt,
    nicht pro Work. Der Charge läuft vor dem Festschreiben der neuen Version, daher
    ist 0 = dies ist der erste (gratis) Loop."""
    return (await db.execute(
        select(func.count(ArtifactVersion.id)).where(ArtifactVersion.artifact_id == artifact_id)
    )).scalar_one()


async def charge_for_run(
    db: AsyncSession, run: WorkRun, *, artifact_id: uuid.UUID | None,
    owner_id: uuid.UUID | None, model: str,
) -> WalletLedger | None:
    """Bucht die Kosten eines fertigen Instanz-Loops vom Guthaben ab. Erster Loop je
    Instanz gratis; idempotent über run_id. Nur Instanz-Läufe (artifact_id gesetzt)
    werden berechnet. Gibt den Buchungsposten zurück (oder None, wenn gratis/bereits
    gebucht/kein Instanz-Lauf)."""
    # Idempotenz
    exists = (await db.execute(
        select(WalletLedger.id).where(WalletLedger.run_id == run.id, WalletLedger.kind == "charge")
    )).first()
    if exists:
        return None
    # Nur Instanz-Läufe werden dem Nutzer berechnet.
    if artifact_id is None or owner_id is None:
        return None
    # Erster Loop der Instanz ist gratis (noch keine Version festgeschrieben).
    if await instance_completed_loops(db, artifact_id) == 0:
        return None

    pin, pout = await model_pricing.price_for(db, model)
    cost = provider_cost(pin, pout, run.total_tokens_in or 0, run.total_tokens_out or 0)
    amount = (cost * MARGIN).quantize(Decimal("0.000001"))

    user = await db.get(User, owner_id)
    if user is None:
        return None
    user.balance_usd = (user.balance_usd or Decimal("0")) - amount
    led = WalletLedger(
        user_id=owner_id, kind="charge", amount_usd=-amount, artifact_id=artifact_id,
        run_id=run.id, model=model, tokens_in=run.total_tokens_in or 0,
        tokens_out=run.total_tokens_out or 0, provider_cost_usd=cost, margin=MARGIN,
        description=f"Lauf {model}",
    )
    db.add(led)
    await _credit_creator_royalty(db, artifact_id=artifact_id, owner_id=owner_id,
                                  cost=cost, model=model)
    return led


async def charge_for_chat_turn(
    db: AsyncSession, *, artifact_id: uuid.UUID, owner_id: uuid.UUID, model: str,
    tokens_in: int, tokens_out: int,
) -> WalletLedger | None:
    """Bucht die Kosten EINES Chat-Laufs vom Guthaben ab. KEIN Gratis-Lauf (anders als
    charge_for_run) — ab dem ersten Turn. Keine Idempotenz nötig (execute_chat_turn
    läuft mit max_retries=0)."""
    if tokens_in == 0 and tokens_out == 0:
        return None
    pin, pout = await model_pricing.price_for(db, model)
    cost = provider_cost(pin, pout, tokens_in, tokens_out)
    amount = (cost * MARGIN).quantize(Decimal("0.000001"))
    user = await db.get(User, owner_id)
    if user is None:
        return None
    user.balance_usd = (user.balance_usd or Decimal("0")) - amount
    led = WalletLedger(
        user_id=owner_id, kind="charge", amount_usd=-amount, artifact_id=artifact_id,
        run_id=None, model=model, tokens_in=tokens_in, tokens_out=tokens_out,
        provider_cost_usd=cost, margin=MARGIN, description=f"Chat-Lauf {model}",
    )
    db.add(led)
    await _credit_creator_royalty(db, artifact_id=artifact_id, owner_id=owner_id,
                                  cost=cost, model=model)
    return led


async def charge_for_router_turn(
    db: AsyncSession, *, owner_id: uuid.UUID, model: str, tokens_in: int, tokens_out: int,
) -> WalletLedger | None:
    """Bucht die Kosten eines Verteiler-Routing-Aufrufs (Haiku) vom Guthaben ab.
    Gehört keiner Instanz → artifact_id=None."""
    if tokens_in == 0 and tokens_out == 0:
        return None
    pin, pout = await model_pricing.price_for(db, model)
    cost = provider_cost(pin, pout, tokens_in, tokens_out)
    amount = (cost * MARGIN).quantize(Decimal("0.000001"))
    user = await db.get(User, owner_id)
    if user is None:
        return None
    user.balance_usd = (user.balance_usd or Decimal("0")) - amount
    led = WalletLedger(
        user_id=owner_id, kind="charge", amount_usd=-amount, artifact_id=None,
        run_id=None, model=model, tokens_in=tokens_in, tokens_out=tokens_out,
        provider_cost_usd=cost, margin=MARGIN, description="Verteiler-Routing")
    db.add(led)
    return led


async def charge_for_image(
    db: AsyncSession, *, artifact_id: uuid.UUID, owner_id: uuid.UUID,
) -> WalletLedger | None:
    """Bucht den Fixpreis eines erzeugten Bildes ($0.02) vom Guthaben ab."""
    user = await db.get(User, owner_id)
    if user is None:
        return None
    amount = IMAGE_PRICE_USD
    cost = (IMAGE_PRICE_USD / MARGIN)
    user.balance_usd = (user.balance_usd or Decimal("0")) - amount
    led = WalletLedger(
        user_id=owner_id, kind="charge", amount_usd=-amount, artifact_id=artifact_id,
        run_id=None, model="gpt-image-1", provider_cost_usd=cost, margin=MARGIN,
        description="Bild erzeugt")
    db.add(led)
    return led
