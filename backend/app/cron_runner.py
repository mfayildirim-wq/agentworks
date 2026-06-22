"""Cron-Runner: Long-running Prozess, der `cron_jobs` periodisch prüft und Runs anstößt.

Start: `python -m app.cron_runner`
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from croniter import croniter
from sqlalchemy import select

from app.core.logging import configure_logging, logger
from app.core.settings import get_settings
from app.db.models import (
    ArtifactJob,
    CronJob,
    RunStatus,
    WorkRun,
)
from app.db.session import SessionLocal

settings = get_settings()
configure_logging(settings.log_level)


async def tick() -> None:
    async with SessionLocal() as db:
        now = datetime.now(UTC)
        rows = (await db.execute(select(CronJob).where(CronJob.enabled.is_(True)))).scalars().all()
        for job in rows:
            base = job.last_run_at or job.created_at
            it = croniter(job.cron_expr, base)
            next_run = it.get_next(datetime)
            if next_run.tzinfo is None:
                next_run = next_run.replace(tzinfo=UTC)
            if next_run > now:
                continue
            run = WorkRun(work_id=job.work_id, status=RunStatus.PENDING)
            db.add(run)
            job.last_run_at = now
            await db.commit()
            await db.refresh(run)
            try:
                from app.workers import execute_run

                execute_run.send(str(run.id))
                logger.info("cron-enqueued", job_id=str(job.id), run_id=str(run.id))
            except Exception:
                logger.exception("cron-enqueue-failed", job_id=str(job.id))


async def tick_jobs() -> None:
    """Fällige `artifact_jobs` abgleichen und die jeweilige Instanz auslösen."""
    from app.services import artifacts as artifact_svc
    from app.services import artifact_jobs as jobs_svc

    async with SessionLocal() as db:
        now = datetime.now(UTC)
        rows = (
            await db.execute(
                select(ArtifactJob).where(ArtifactJob.status.in_(("scheduled", "active")))
            )
        ).scalars().all()
        for j in rows:
            # 1) Reconcile: Vorlauf-Ergebnis verbuchen.
            if j.last_run_id is not None:
                prev = await db.get(WorkRun, j.last_run_id)
                if prev is not None:
                    if prev.status in (RunStatus.PENDING, RunStatus.RUNNING):
                        continue
                    jobs_svc.apply_run_outcome(j, prev.status, prev.error)
                    if j.status == "paused":
                        await db.commit()
                        continue

            # 2) Fälligkeit.
            nxt = jobs_svc.compute_next_run(j, now)
            if nxt is None or nxt > now:
                await db.commit()
                continue

            # 3) Auslösen: bestehende Instanz, notify_owner falls Mail/Telegram gewünscht.
            notify = bool(j.notify_email or j.notify_telegram)
            run_id = await artifact_svc.adjust(
                db, j.artifact_id, j.owner_id, j.instruction,
                notify_owner=notify, notify_chat=j.notify_chat, mode=j.mode,
            )
            if run_id is None:
                continue
            j.last_run_at = now
            j.last_run_id = run_id
            j.run_count += 1
            j.next_run_at = jobs_svc.compute_next_run(j, now)
            if j.trigger_kind == "once":
                j.status = "completed"
            await db.commit()
            logger.info("job-enqueued", job_id=str(j.id), run_id=str(run_id))


# Telegram-getUpdates-Offset (Prozess-Speicher). Verlust bei Neustart ist unkritisch:
# das Verbinden ist idempotent, alte Updates werden höchstens einmal neu verarbeitet.
_tg_offset = 0


async def tick_telegram() -> None:
    """Telegram-Poller: verarbeitet `/start <token>` zum Verbinden des Kontos."""
    global _tg_offset
    from app.services.notify import channels, telegram_link

    if not channels.telegram_configured():
        return
    data = await channels.telegram_api("getUpdates", {"offset": _tg_offset, "timeout": 0})
    for upd in data.get("result", []):
        _tg_offset = max(_tg_offset, upd["update_id"] + 1)
        msg = upd.get("message") or {}
        text = (msg.get("text") or "").strip()
        chat_id = (msg.get("chat") or {}).get("id")
        if chat_id is None or not text:
            continue
        if text.startswith("/start"):
            parts = text.split(maxsplit=1)
            token = parts[1].strip() if len(parts) > 1 else ""
            async with SessionLocal() as db:
                user = await telegram_link.handle_start(db, token, str(chat_id))
            reply = (
                "✅ Verbunden! Du bekommst ab jetzt Benachrichtigungen hier."
                if user
                else "Hi! Bitte verbinde dich über „Profil → Benachrichtigungen“ auf der Website."
            )
            try:
                await channels.telegram_api("sendMessage", {"chat_id": chat_id, "text": reply})
            except Exception:
                logger.exception("telegram-reply-failed")
            continue
        # Normale Nachricht → Verteiler. Sofort-Antwort (Link/Guthaben/Rückfrage) → senden;
        # None = Turn läuft im Worker, der die Antwort selbst zurückschickt (kein Poller-Block).
        from app.services import channel_dispatch
        try:
            async with SessionLocal() as db:
                reply = await channel_dispatch.handle_inbound(db, "telegram", str(chat_id), text)
            if reply is not None:
                await channels.telegram_api("sendMessage", {"chat_id": chat_id, "text": reply})
        except Exception:
            logger.exception("telegram-dispatch-failed")


async def main() -> None:
    logger.info("cron-runner-start")
    while True:
        try:
            await tick()
        except Exception:
            logger.exception("cron-tick-failed")
        try:
            await tick_jobs()
        except Exception:
            logger.exception("job-tick-failed")
        try:
            await tick_telegram()
        except Exception:
            logger.exception("telegram-tick-failed")
        await asyncio.sleep(30)


if __name__ == "__main__":
    asyncio.run(main())
