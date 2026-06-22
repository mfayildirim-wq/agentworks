"""Stripe-Checkout-Anbindung (gehostete Bezahlseite). Lazy-Import von `stripe`,
damit Tests die Funktionen monkeypatchen können, ohne die Lib zu brauchen.
Alle Aufrufe scheitern freundlich (kein Secret/Stacktrace nach außen)."""
from __future__ import annotations

import logging
from decimal import Decimal

from app.core.settings import get_settings

settings = get_settings()
log = logging.getLogger(__name__)


def is_configured() -> bool:
    return bool(settings.stripe_secret_key)


def create_checkout_session(amount_usd: Decimal, *, user_id, success_url: str,
                            cancel_url: str) -> str | None:
    """Erstellt eine Checkout-Session und gibt die Bezahl-URL zurück (oder None bei Fehler)."""
    if not is_configured():
        return None
    try:
        import stripe
        stripe.api_key = settings.stripe_secret_key
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "unit_amount": int((amount_usd * 100).to_integral_value()),
                    "product_data": {"name": "AgentWorks Guthaben"},
                },
                "quantity": 1,
            }],
            success_url=success_url,
            cancel_url=cancel_url,
            client_reference_id=str(user_id),
            metadata={"user_id": str(user_id), "amount_usd": str(amount_usd)},
        )
        return session.url
    except Exception:
        log.exception("Stripe create_checkout_session fehlgeschlagen")
        return None


def retrieve_paid_amount(session_id: str) -> tuple[bool, Decimal, str | None]:
    """(paid, amount_usd, client_reference_id). Fehler/ungültig → (False, 0, None)."""
    if not is_configured():
        return (False, Decimal("0"), None)
    try:
        import stripe
        stripe.api_key = settings.stripe_secret_key
        s = stripe.checkout.Session.retrieve(session_id)
        paid = getattr(s, "payment_status", None) == "paid"
        amount = Decimal(getattr(s, "amount_total", 0) or 0) / 100
        ref = getattr(s, "client_reference_id", None)
        return (paid, amount, ref)
    except Exception:
        log.exception("Stripe retrieve_paid_amount fehlgeschlagen")
        return (False, Decimal("0"), None)
