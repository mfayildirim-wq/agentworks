"""Dramatiq Worker: führt Work-Runs aus.

Start: `dramatiq app.workers`
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import dramatiq
from agent_runtime.events import RunEvent
from agent_runtime.executor import ExecutorContext
from agent_runtime.executors.factory import create_executor
from dramatiq.brokers.redis import RedisBroker

from app.core.logging import configure_logging, logger
from app.core.settings import get_settings
from app.db.models import RunStatus, WorkRun
from app.db.session import SessionLocal, engine
from app.services import event_bus
from app.services import runs as run_svc

settings = get_settings()
configure_logging(settings.log_level)

broker = RedisBroker(url=settings.redis_url)
dramatiq.set_broker(broker)


async def _post_low_balance_message(db, artifact_id: UUID) -> None:
    """Hinweis in den Instanz-Chat, dass das Guthaben aufgebraucht ist."""
    from app.db.models import ArtifactMessage

    db.add(
        ArtifactMessage(
            artifact_id=artifact_id,
            role="assistant",
            content=(
                "💳 Dein Guthaben ist aufgebraucht. Bitte im Profil aufladen, "
                "um diese Instanz weiter zu nutzen."
            ),
        )
    )
    await db.commit()


@dramatiq.actor(queue_name="runs", max_retries=0, time_limit=15 * 60_000)
def execute_run(run_id: str) -> None:
    asyncio.run(_execute_run_async(UUID(run_id)))


@dramatiq.actor(queue_name="runs", max_retries=0, time_limit=15 * 60_000)
def execute_chat_turn(artifact_id: str) -> None:
    """Dialog-Turn (Phase: konversationelle Instanzen): ein LLM-Aufruf, Ausgabe in
    Chat-Nachricht (+ optional neue Canvas-Version) splitten."""
    asyncio.run(_execute_chat_turn_async(UUID(artifact_id)))


@dramatiq.actor(queue_name="runs", max_retries=0, time_limit=15 * 60_000)
def execute_channel_turn(channel: str, channel_user_id: str, artifact_id: str,
                         owner_id: str, text: str) -> None:
    """Messenger-Turn (Verteiler): Chat-Turn an der Instanz im Worker (blockiert nicht
    den Poller), Antwort danach über den Kanal zurückschicken."""
    asyncio.run(_execute_channel_turn_async(channel, channel_user_id, UUID(artifact_id),
                                            UUID(owner_id), text))


async def _execute_channel_turn_async(channel: str, channel_user_id: str, artifact_id: UUID,
                                      owner_id: UUID, text: str) -> None:
    from app.services import channel_dispatch
    reply = "⚠️ Es gab einen Fehler bei der Antwort. Bitte erneut versuchen."
    try:
        try:
            async with SessionLocal() as db:
                reply = await channel_dispatch.run_instance_turn(
                    db, artifact_id=artifact_id, owner_id=owner_id, text=text)
        except Exception:
            logger.exception("channel-turn-failed", artifact_id=str(artifact_id))
        try:
            await channel_dispatch.send_reply(channel, channel_user_id, reply)
        except Exception:
            logger.exception("channel-reply-failed", channel=channel)
    finally:
        await engine.dispose()


async def _execute_chat_turn_async(artifact_id: UUID) -> None:
    try:
        from decimal import Decimal

        from app.db.models import Artifact, ArtifactMessage, User
        from app.services import artifact_chat
        from app.services import artifact_chat_runtime as rt
        from app.services import billing

        try:
            async with SessionLocal() as db:
                # Guthaben-Schutz VOR dem Lauf.
                art = await db.get(Artifact, artifact_id)
                owner = await db.get(User, art.owner_id) if art else None
                if owner is not None and (owner.balance_usd or Decimal("0")) <= 0:
                    db.add(ArtifactMessage(
                        artifact_id=artifact_id, role="assistant",
                        content="💳 Dein Guthaben ist aufgebraucht. Bitte lade es auf, "
                                "um fortzufahren."))
                    await db.commit()
                    return

                complete, meta = await rt.make_completer(db, artifact_id)
                await artifact_chat.run_turn(
                    db, artifact_id=artifact_id, complete=complete
                )
                # Abrechnung NACH dem Turn (best-effort).
                try:
                    await billing.charge_for_chat_turn(
                        db, artifact_id=artifact_id, owner_id=meta.owner_id,
                        model=meta.model, tokens_in=meta.tokens_in,
                        tokens_out=meta.tokens_out)
                    await db.commit()
                except Exception:
                    logger.exception("billing-chat-charge-failed",
                                     artifact_id=str(artifact_id))
        except Exception:
            logger.exception("chat-turn-failed", artifact_id=str(artifact_id))
            # Fehler sichtbar machen, damit das Frontend-Polling nicht ewig wartet.
            async with SessionLocal() as db:
                db.add(
                    ArtifactMessage(
                        artifact_id=artifact_id,
                        role="assistant",
                        content="⚠️ Es gab einen Fehler bei der Antwort. Bitte erneut versuchen.",
                    )
                )
                await db.commit()
    finally:
        await engine.dispose()


async def _execute_run_async(run_id: UUID) -> None:
    # Jede dramatiq-Nachricht läuft in einem eigenen Event-Loop (asyncio.run).
    # Die globale async-Engine poolt Verbindungen pro Loop → ohne Dispose am Ende
    # bindet die nächste Nachricht eine alte Verbindung an einen fremden Loop
    # ("got Future attached to a different loop"). Darum nach jeder Nachricht disposen.
    try:
        await _run_impl(run_id)
    finally:
        await engine.dispose()


async def _run_impl(run_id: UUID) -> None:
    async with SessionLocal() as db:
        run = await db.get(WorkRun, run_id)
        if run is None:
            logger.error("run-missing", run_id=str(run_id))
            return
        run.status = RunStatus.RUNNING
        await db.commit()

        try:
            work_spec = await run_svc.build_work_spec(db, run_id)
        except Exception as exc:
            logger.exception("build-spec-failed", run_id=str(run_id))
            run.status = RunStatus.FAILED
            run.error = str(exc)
            run.finished_at = datetime.now(UTC)
            await db.commit()
            return

        loop = asyncio.get_event_loop()
        pending: list[RunEvent] = []

        def on_event(event: RunEvent) -> None:
            pending.append(event)
            asyncio.run_coroutine_threadsafe(
                event_bus.publish(run_id, event), loop
            )

        # Phase 2c: Bei Instanz-Läufen (artifact_id in der loop_config) Web-Tools injizieren,
        # damit ein tool-fähiges Modell frische Daten holen kann. Kein Scheduling im
        # automatischen Lauf (allow_scheduling=False); das Provider-Gating macht der Executor.
        run_tools: list = []
        _work = None
        _target = None
        try:
            from app.db.models import Artifact, Work
            from app.services.agent_tools import build_tools

            _work = await db.get(Work, run.work_id)
            _cfg = (_work.loop_config or {}) if _work else {}
            _target = _cfg.get("artifact_id")
            if _target:
                _art = await db.get(Artifact, UUID(_target))
                if _art is not None:
                    run_tools = build_tools(
                        artifact_id=_art.id, owner_id=_art.owner_id, allow_scheduling=False
                    )
        except Exception:
            logger.exception("run-tools-build-failed", run_id=str(run_id))

        ctx = ExecutorContext(
            api_key=settings.anthropic_api_key,
            on_event=on_event,
            ollama_url=settings.ollama_url,
            tools=run_tools,
        )
        # Budget-Deckel: abgerechnete Instanz-Loops nur mit Guthaben starten.
        # Gratis-Lauf (erste Version der Instanz) ist ausgenommen.
        if work_spec.loop and work_spec.loop.enabled and _target:
            from app.db.models import User
            from app.services import billing

            if await billing.instance_completed_loops(db, UUID(_target)) >= 1:
                _owner = await db.get(User, _work.owner_id) if _work else None
                budget = (
                    await billing.remaining_run_budget(db, _owner)
                    if _owner
                    else Decimal("0")
                )
                if budget <= 0:
                    run.status = RunStatus.FAILED
                    run.error = "Guthaben aufgebraucht"
                    run.finished_at = datetime.now(UTC)
                    await db.commit()
                    await _post_low_balance_message(db, UUID(_target))
                    logger.info("run-skipped-no-balance", run_id=str(run_id))
                    return
                work_spec.loop.max_cost_usd = float(budget)

        if work_spec.loop and work_spec.loop.enabled:
            from agent_runtime.executors.goal_loop import GoalLoopExecutor

            executor = GoalLoopExecutor()
        else:
            executor = create_executor(work_spec.mode)

        try:
            result = await executor.run(work_spec, ctx)
        except Exception as exc:
            logger.exception("executor-failed", run_id=str(run_id))
            run.status = RunStatus.FAILED
            run.error = str(exc)
            run.finished_at = datetime.now(UTC)
            # persist pending events even on failure
            for event in pending:
                await event_bus.persist(db, event)
            await db.commit()
            return

        for event in pending:
            await event_bus.persist(db, event)

        run.status = RunStatus.COMPLETED
        run.total_tokens_in = result.total_tokens_in
        run.total_tokens_out = result.total_tokens_out
        run.total_cost = result.total_cost_usd
        run.result = {"final_message": result.final_message, **result.metadata}
        run.finished_at = datetime.now(UTC)
        await db.commit()
        logger.info("run-completed", run_id=str(run_id), cost=result.total_cost_usd)

        # Abrechnung: Kosten dieses Loops vom Guthaben abziehen (erster Loop gratis).
        try:
            from app.db.models import Work
            from app.services import billing

            _bwork = await db.get(Work, run.work_id)
            _bcfg = (_bwork.loop_config or {}) if _bwork else {}
            _bart = _bcfg.get("artifact_id")
            _bmodel = work_spec.agents[0].model if work_spec.agents else settings.default_model
            await billing.charge_for_run(
                db, run,
                artifact_id=UUID(_bart) if _bart else None,
                owner_id=_bwork.owner_id if _bwork else None,
                model=_bmodel,
            )
            await db.commit()
        except Exception:
            logger.exception("billing-charge-failed", run_id=str(run_id))

        # Artefakt-Version best-effort NACH der Run-Finalisierung: ein Fehler hier
        # (Datei-IO, DB) darf den bereits committeten Run nicht in einen halben
        # Zustand bringen.
        artifact_html = result.metadata.get("artifact")
        version = None
        notify_owner = False
        notify_chat = False
        if artifact_html and work_spec.loop and work_spec.loop.enabled:
            try:
                from app.db.models import Work
                from app.services import artifact_schedules as sched_svc
                from app.services import artifacts as artifact_svc

                work = await db.get(Work, run.work_id)
                cfg = (work.loop_config or {}) if work else {}
                # Ziel-Instanz (Phase 5d): die artifact_id steht in der loop_config des Works.
                target = cfg.get("artifact_id")
                notify_owner = bool(cfg.get("notify_owner"))
                notify_chat = bool(cfg.get("notify_chat"))
                if target:
                    # Schritt 3: SCHEDULE-Marker des Agenten aus dem HTML ziehen,
                    # daraus eine Selbst-Aktualisierung anlegen, Marker entfernen.
                    clean_html, directives = sched_svc.extract_schedule_directives(
                        artifact_html
                    )
                    version = await artifact_svc.record_version_placed(
                        db,
                        artifact_id=UUID(target),
                        content=clean_html,
                        prompt=work.goal,
                        run_id=run.id,
                    )
                    if directives:
                        cadence, instruction = directives[0]
                        from app.services import artifact_jobs as jobs_svc

                        await jobs_svc.upsert_from_agent(
                            db, UUID(target), cadence=cadence.value, instruction=instruction
                        )
                        logger.info(
                            "job-set-by-agent", run_id=str(run_id), cadence=cadence.value
                        )
            except Exception:
                logger.exception("artifact-record-failed", run_id=str(run_id))

        # Benachrichtigung (geplantes Update): eigener best-effort-Block, damit ein
        # Versandfehler den bereits finalisierten Lauf nicht beeinflusst.
        if notify_owner and version is not None:
            try:
                from app.core.settings import get_settings
                from app.db.models import Artifact, User
                from app.services.notify import dispatch, messages

                art = await db.get(Artifact, version.artifact_id)
                owner = await db.get(User, art.owner_id) if art else None
                if owner is not None:
                    base = get_settings().public_base_url.rstrip("/")
                    url = f"{base}/artifacts/{art.id}"
                    await dispatch.notify_user(
                        owner,
                        messages.update_subject(art.title, version.version_no),
                        messages.update_body(art.title, version.version_no, url),
                        url,
                    )
                    logger.info("notify-sent", run_id=str(run_id), artifact_id=str(art.id))
            except Exception:
                logger.exception("notify-failed", run_id=str(run_id))

        # Phase 2c: notify_chat → Update als Assistant-Nachricht in den Instanz-Chat schreiben.
        if notify_chat and version is not None:
            try:
                from app.core.settings import get_settings
                from app.db.models import Artifact, ArtifactMessage
                from app.services.notify import messages

                art_c = await db.get(Artifact, version.artifact_id)
                if art_c is not None:
                    base = get_settings().public_base_url.rstrip("/")
                    url = f"{base}/artifacts/{art_c.id}"
                    db.add(
                        ArtifactMessage(
                            artifact_id=art_c.id,
                            role="assistant",
                            content=messages.update_chat_text(
                                art_c.title, version.version_no, url
                            ),
                            version_id=version.id,
                        )
                    )
                    await db.commit()
                    logger.info(
                        "notify-chat-posted", run_id=str(run_id), artifact_id=str(art_c.id)
                    )
            except Exception:
                logger.exception("notify-chat-failed", run_id=str(run_id))

        # Phase: Agent-Verkettung — bei erfolgreichem neuen Stand die Folge-Instanz auto-feuern.
        if version is not None:
            try:
                from app.db.models import Artifact
                from app.services import chains
                src = await db.get(Artifact, version.artifact_id)
                if src is not None and src.chain_auto and src.next_artifact_id is not None:
                    await chains.forward(db, src.id)
                    logger.info("chain-forwarded", run_id=str(run_id), src=str(src.id))
            except Exception:
                logger.exception("chain-forward-failed", run_id=str(run_id))

        # Message-Timer (reminder): kein Canvas/keine Version — Agenten-Text zustellen.
        try:
            from app.db.models import Work

            _w = await db.get(Work, run.work_id)
            _cfg = (_w.loop_config or {}) if _w else {}
            if _cfg.get("job_mode") == "reminder" and _cfg.get("artifact_id"):
                from app.core.settings import get_settings
                from app.db.models import Artifact, ArtifactMessage, User
                from app.services.notify import dispatch
                from app.services.notify import messages as notify_messages

                target_id = UUID(_cfg["artifact_id"])
                art_r = await db.get(Artifact, target_id)
                text = notify_messages.reminder_chat_text(result.final_message or "")
                if art_r is not None and not text:
                    # Leerer Agenten-Text (z.B. nur Tool-Calls/Token-Limit): nichts
                    # zugestellt — sichtbar machen, sonst verschwindet der Reminder still.
                    logger.warning("reminder-empty-text", run_id=str(run_id),
                                   artifact_id=str(target_id))
                if art_r is not None and text:
                    db.add(ArtifactMessage(
                        artifact_id=target_id, role="assistant", content=text))
                    await db.commit()
                    logger.info("reminder-posted", run_id=str(run_id),
                                artifact_id=str(target_id))
                    if bool(_cfg.get("notify_owner")):
                        owner_r = await db.get(User, art_r.owner_id)
                        if owner_r is not None:
                            base = get_settings().public_base_url.rstrip("/")
                            url = f"{base}/artifacts/{art_r.id}"
                            await dispatch.notify_user(
                                owner_r, notify_messages.reminder_subject(art_r.title),
                                text, url)
        except Exception:
            logger.exception("reminder-failed", run_id=str(run_id))
