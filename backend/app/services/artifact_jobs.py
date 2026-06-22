from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from croniter import croniter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Artifact, ArtifactJob, RunStatus
from app.schemas.artifacts import JobOut

_CADENCE_CRON: dict[str, str] = {
    "hourly": "0 * * * *",
    "daily": "0 6 * * *",
    "weekly": "0 6 * * 1",
}
_FAIL_LIMIT = 3

# Backfill aus artifact_schedules (von Migration 0012 UND dem Test genutzt — eine Quelle).
BACKFILL_SCHEDULES_SQL = """
INSERT INTO artifact_jobs
  (id, artifact_id, owner_id, title, instruction, trigger_kind, cadence, cron_expr,
   run_at, status, next_run_at, last_run_at, last_run_id, run_count, fail_count,
   notify_email, notify_telegram, notify_chat, created_by, created_at, updated_at)
SELECT
  gen_random_uuid(), artifact_id, owner_id, 'Automatische Aktualisierung',
  refresh_instruction,
  CASE WHEN completion_mode = 'once' THEN 'once' ELSE 'recurring' END,
  cadence::text, cron_expr, NULL,
  status::text, NULL, last_run_at, last_run_id, run_count, fail_count,
  true, true, false, 'system', created_at, updated_at
FROM artifact_schedules
WHERE enabled = true
"""


def cron_for(cadence: str) -> str:
    return _CADENCE_CRON[cadence]


def compute_next_run(job: ArtifactJob, now: datetime | None = None) -> datetime | None:
    now = now or datetime.now(UTC)
    if job.trigger_kind == "once":
        return None if job.last_run_at is not None else job.run_at
    if not job.cron_expr:
        return None
    base = job.last_run_at or job.created_at or now
    nxt = croniter(job.cron_expr, base).get_next(datetime)
    if nxt.tzinfo is None:
        nxt = nxt.replace(tzinfo=UTC)
    return nxt


# Fehler, die NICHT die Schuld des Jobs sind (Plattform/vorübergehend): ungültiger
# Platform-Key, Rate-Limit, Überlastung, leeres Guthaben. Solche Fehlläufe dürfen den
# Timer nicht dauerhaft pausieren — sonst killt ein einzelner Key-Ausfall alle Timer.
_TRANSIENT_ERROR_MARKERS = (
    "invalid x-api-key",
    "authentication_error",
    "rate_limit",
    "429",
    "overloaded",
    "guthaben aufgebraucht",
    "insufficient",
    "service unavailable",
    "503",
)


def is_transient_error(error: str | None) -> bool:
    """True, wenn der Run-Fehler plattform-/abrechnungsseitig (vorübergehend) ist."""
    if not error:
        return False
    e = error.lower()
    return any(marker in e for marker in _TRANSIENT_ERROR_MARKERS)


def apply_run_outcome(
    job: ArtifactJob, run_status: RunStatus, error: str | None = None
) -> None:
    if run_status == RunStatus.COMPLETED:
        job.fail_count = 0
    elif run_status == RunStatus.FAILED:
        # Plattform-/vorübergehende Fehler nicht anrechnen: der Timer bleibt aktiv und
        # versucht es im nächsten Zyklus erneut (Selbstheilung nach Key-/Guthaben-Fix).
        if is_transient_error(error):
            return
        job.fail_count += 1
        if job.fail_count >= _FAIL_LIMIT:
            job.status = "paused"


def to_out(job: ArtifactJob) -> JobOut:
    out = JobOut.model_validate(job)
    out.next_run_at = compute_next_run(job)
    return out


async def _owned(db: AsyncSession, artifact_id: UUID, owner_id: UUID) -> Artifact | None:
    """Liefert das Artefakt nur, wenn es dem Nutzer gehört — sonst None."""
    art = await db.get(Artifact, artifact_id)
    if art is None or art.owner_id != owner_id:
        return None
    return art


async def list_for_artifact(
    db: AsyncSession, artifact_id: UUID, owner_id: UUID
) -> list[JobOut] | None:
    """Jobs einer Instanz — None, wenn die Instanz dem Nutzer nicht gehört."""
    if await _owned(db, artifact_id, owner_id) is None:
        return None
    stmt = (
        select(ArtifactJob)
        .where(ArtifactJob.artifact_id == artifact_id)
        .order_by(ArtifactJob.created_at.asc())
    )
    rows = list((await db.execute(stmt)).scalars().all())
    return [to_out(j) for j in rows]


async def active_counts(db: AsyncSession, owner_id: UUID) -> dict[UUID, int]:
    """Anzahl aktiver Jobs je Instanz für einen Nutzer."""
    stmt = select(ArtifactJob.artifact_id).where(
        ArtifactJob.owner_id == owner_id,
        ArtifactJob.status == "active",
    )
    counts: dict[UUID, int] = {}
    for (aid,) in (await db.execute(stmt)).all():
        counts[aid] = counts.get(aid, 0) + 1
    return counts


async def upsert_from_agent(
    db: AsyncSession, artifact_id: UUID, *, cadence: str, instruction: str,
    mode: str = "update",
) -> ArtifactJob | None:
    """Vom Agenten (Worker) gesetzter wiederkehrender Auto-Job. Idempotent: genau ein
    `created_by='agent'`-Recurring-Job pro Instanz wird angelegt/aktualisiert."""
    art = await db.get(Artifact, artifact_id)
    if art is None:
        return None
    stmt = select(ArtifactJob).where(
        ArtifactJob.artifact_id == artifact_id,
        ArtifactJob.created_by == "agent",
        ArtifactJob.trigger_kind == "recurring",
    )
    job = (await db.execute(stmt)).scalars().first()
    if job is None:
        job = ArtifactJob(
            artifact_id=artifact_id, owner_id=art.owner_id, created_by="agent",
            title="Automatische Aktualisierung", trigger_kind="recurring",
            notify_email=True, notify_telegram=True, mode=mode,
        )
        db.add(job)
    job.mode = mode
    job.cadence = cadence
    job.cron_expr = cron_for(cadence)
    job.instruction = instruction
    job.status = "active"
    job.fail_count = 0
    await db.commit()
    await db.refresh(job)
    return job


async def create_job_from_tool(
    db: AsyncSession,
    *,
    artifact_id: UUID,
    owner_id: UUID,
    title: str,
    instruction: str,
    trigger_kind: str,
    cadence: str | None = None,
    cron_expr: str | None = None,
    run_at: datetime | None = None,
    notify_email: bool = False,
    notify_telegram: bool = False,
    notify_chat: bool = True,
    mode: str = "update",
) -> ArtifactJob | None:
    """Vom Agenten via Tool angelegte EIGENE Aufgabe (mehrere pro Instanz möglich).

    Owner-geprüft. Abgegrenzt von `upsert_from_agent` (dem einzelnen Auto-Refresh-Job).
    """
    if await _owned(db, artifact_id, owner_id) is None:
        return None
    job = ArtifactJob(
        artifact_id=artifact_id,
        owner_id=owner_id,
        created_by="agent",
        title=title or "Aufgabe",
        instruction=instruction,
        trigger_kind="once" if trigger_kind == "once" else "recurring",
        cadence=cadence,
        cron_expr=cron_expr,
        run_at=run_at,
        status="active",
        notify_email=notify_email,
        notify_telegram=notify_telegram,
        notify_chat=notify_chat,
        mode=mode,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def cancel_job(db: AsyncSession, job_id: UUID, owner_id: UUID) -> bool:
    """Setzt einen Job der Instanz auf 'completed' (Owner-geprüft)."""
    job = await db.get(ArtifactJob, job_id)
    if job is None or job.owner_id != owner_id:
        return False
    job.status = "completed"
    await db.commit()
    return True
