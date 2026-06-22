"""Channel-neutraler Verteiler: eingehende Nachricht → passende eigene Instanz →
Chat-Turn → Antworttext. Nutzer-Auflösung + sticky aktive Instanz + Rückfrage."""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from app.db.models import Artifact, ArtifactMessage, ChannelSession, Template, User
from app.services import billing, router_agent

_TOPUP = "💳 Dein Guthaben ist aufgebraucht. Bitte lade es auf, um fortzufahren."
_LINK = "Bitte verbinde dein Konto über Profil → Benachrichtigungen auf der Website."
_NONE = "Du hast noch keine Agenten-Instanz, die antworten könnte."
_ERR = "⚠️ Es gab einen Fehler bei der Antwort. Bitte erneut versuchen."
# Fix 3: nicht ALLE Instanzen in den Router-Prompt — die zuletzt genutzten reichen
# (kürzerer/billigerer Prompt, übersichtlichere Rückfrage).
_MAX_CANDIDATES = 12


async def _resolve_user(db, channel: str, channel_user_id: str) -> User | None:
    if channel == "telegram":
        return (await db.execute(
            select(User).where(User.telegram_chat_id == channel_user_id))).scalars().first()
    return None


async def _candidates(db, owner_id) -> list[dict]:
    arts = (await db.execute(select(Artifact).where(Artifact.owner_id == owner_id)
            .order_by(Artifact.updated_at.desc()).limit(_MAX_CANDIDATES))).scalars().all()
    out = []
    for a in arts:
        desc = ""
        if a.template_id is not None:
            tpl = await db.get(Template, a.template_id)
            desc = (tpl.description if tpl else "") or ""
        out.append({"artifact_id": a.id, "title": a.title or "Instanz", "description": desc})
    return out


def _ask_text(candidates: list) -> str:
    opts = " ".join(f"{c['n']}) {c['title']}" for c in candidates)
    return f"Welchen Agenten meinst du? {opts} — antworte mit der Zahl."


async def run_instance_turn(db, *, artifact_id, owner_id, text) -> str:
    """Führt den Chat-Turn an der Instanz aus und gibt den Antworttext zurück.
    Läuft im WORKER (eigene Session) — committet selbst. Schwere/Tool-lastige Turns
    blockieren so nicht mehr den Telegram-Poller (Fix 1)."""
    from app.services import artifact_chat
    from app.services import artifact_chat_runtime as rt
    user = await db.get(User, owner_id)
    if user is None:
        return _ERR
    if (user.balance_usd or Decimal("0")) <= 0:
        return _TOPUP
    try:
        # WICHTIG: Nutzer-Nachricht COMMITTEN (nicht nur flush) bevor der Turn läuft.
        # Sonst hält die offene Transaktion einen FK-Share-Lock auf die Artefakt-Zeile,
        # und die slot-Tools (eigene Session) blockieren beim UPDATE der Zeile bis zum
        # 15-Min-Time-Limit (= keine Antwort). Der Web-Pfad committet die User-Msg ebenso vorab.
        db.add(ArtifactMessage(artifact_id=artifact_id, role="user", content=text))
        await db.commit()
        complete, meta = await rt.make_completer(db, artifact_id)
        await artifact_chat.run_turn(db, artifact_id=artifact_id, complete=complete)
    except Exception:
        # z.B. defekte Instanz (kein Agent/keine Version) → freundlicher Fehler statt Crash.
        return _ERR
    try:
        await billing.charge_for_chat_turn(db, artifact_id=artifact_id, owner_id=owner_id,
                                           model=meta.model, tokens_in=meta.tokens_in,
                                           tokens_out=meta.tokens_out)
        await db.commit()
    except Exception:
        pass
    # Antworttext per frischer Query holen (nach den Commits ist ein ORM-Objekt „expired"
    # → msg.content würde im async-Kontext brechen). Neueste Assistant-Nachricht der Instanz.
    reply = (await db.execute(
        select(ArtifactMessage.content)
        .where(ArtifactMessage.artifact_id == artifact_id, ArtifactMessage.role == "assistant")
        .order_by(ArtifactMessage.created_at.desc()).limit(1))).scalars().first()
    # Fix 2: Canvas/Slot-Agenten antworten teils nur mit einer Seiten-Aktualisierung (kein
    # Chat-Text). Über einen Textkanal MUSS etwas Sinnvolles ankommen → Hinweis + Link.
    if not (reply or "").strip():
        from app.core.settings import get_settings
        base = get_settings().public_base_url.rstrip("/")
        reply = f"✅ Deine Seite wurde aktualisiert:\n{base}/artifacts/{artifact_id}"
    return reply


def _enqueue_turn(channel: str, channel_user_id: str, artifact_id, owner_id, text: str) -> None:
    """Turn an den Worker übergeben (asynchron); der Worker schickt die Antwort zurück."""
    from app.workers import execute_channel_turn
    execute_channel_turn.send(channel, channel_user_id, str(artifact_id), str(owner_id), text)


async def send_reply(channel: str, channel_user_id: str, text: str) -> None:
    """Antwort über den jeweiligen Kanal ausliefern (vom Worker aufgerufen)."""
    if channel == "telegram":
        from app.core.settings import get_settings
        from app.services.notify import channels
        await channels.send_telegram(channel_user_id, text, get_settings().public_base_url)


async def handle_inbound(db, channel: str, channel_user_id: str, text: str) -> str | None:
    """Synchrone Routing-Entscheidung. Sofort-Antwort (Link/Guthaben/Rückfrage/keine
    Instanz) → Text zurück. Turn-Fall → in den Worker enqueuen + None (der Worker
    liefert die Antwort asynchron über send_reply)."""
    user = await _resolve_user(db, channel, channel_user_id)
    if user is None:
        return _LINK
    if (user.balance_usd or Decimal("0")) <= 0:
        return _TOPUP

    sess = (await db.execute(select(ChannelSession).where(
        ChannelSession.channel == channel,
        ChannelSession.channel_user_id == channel_user_id))).scalars().first()
    if sess is not None and sess.user_id != user.id:
        # Kanal wurde an ein anderes Konto neu verknüpft → veraltete Session (inkl.
        # fremder pending-Kandidaten/aktiver Instanz) verwerfen, NIE übernehmen.
        await db.delete(sess)
        await db.flush()
        sess = None
    if sess is None:
        sess = ChannelSession(channel=channel, channel_user_id=channel_user_id, user_id=user.id)
        db.add(sess); await db.flush()

    if sess.pending:
        cands = sess.pending.get("candidates", [])
        orig = sess.pending.get("text", text)
        choice = None
        try:
            n = int(text.strip())
            choice = next((c for c in cands if c["n"] == n), None)
        except Exception:
            choice = None
        if choice is None:
            return _ask_text(cands)
        sess.active_artifact_id = UUID(str(choice["artifact_id"]))
        sess.pending = None
        await db.commit()
        _enqueue_turn(channel, channel_user_id, sess.active_artifact_id, user.id, orig)
        return None

    cands = await _candidates(db, user.id)
    if not cands:
        return _NONE
    if len(cands) == 1:
        sess.active_artifact_id = cands[0]["artifact_id"]
    else:
        decision = await router_agent.route(db, user.id, message=text,
                                            active=sess.active_artifact_id, candidates=cands)
        if decision.action == "ask":
            sess.pending = {"candidates": [
                {"n": c["n"], "artifact_id": str(c["artifact_id"]), "title": c["title"]}
                for c in decision.candidates], "text": text}
            await db.commit()
            return _ask_text(sess.pending["candidates"])
        sess.active_artifact_id = decision.artifact_id

    await db.commit()
    _enqueue_turn(channel, channel_user_id, sess.active_artifact_id, user.id, text)
    return None
