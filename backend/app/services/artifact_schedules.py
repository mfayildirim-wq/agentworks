from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID

from croniter import croniter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Artifact,
    ArtifactSchedule,
    RunStatus,
    ScheduleCadence,
    ScheduleCompletion,
    ScheduleStatus,
)
from app.schemas.artifacts import ScheduleOut

# Preset → cron (fixe UTC-Zeiten, v1). Eigene Uhrzeiten/Wochentage = spätere Ausbaustufe.
_CADENCE_CRON: dict[ScheduleCadence, str] = {
    ScheduleCadence.HOURLY: "0 * * * *",
    ScheduleCadence.DAILY: "0 6 * * *",
    ScheduleCadence.WEEKLY: "0 6 * * 1",
}

_FAIL_LIMIT = 3


def cron_for(cadence: ScheduleCadence) -> str:
    return _CADENCE_CRON[cadence]


def compute_next_run(schedule: ArtifactSchedule, now: datetime | None = None) -> datetime:
    base = schedule.last_run_at or schedule.created_at or (now or datetime.now(UTC))
    nxt = croniter(schedule.cron_expr, base).get_next(datetime)
    if nxt.tzinfo is None:
        nxt = nxt.replace(tzinfo=UTC)
    return nxt


def apply_run_outcome(schedule: ArtifactSchedule, run_status: RunStatus) -> None:
    """Reconcile-Schritt (rein, ohne DB): Fehlerzähler/Status anhand des Vorlaufs anpassen."""
    if run_status == RunStatus.COMPLETED:
        schedule.fail_count = 0
    elif run_status == RunStatus.FAILED:
        schedule.fail_count += 1
        if schedule.fail_count >= _FAIL_LIMIT:
            schedule.status = ScheduleStatus.PAUSED


def to_out(schedule: ArtifactSchedule) -> ScheduleOut:
    out = ScheduleOut.model_validate(schedule)
    out.next_run_at = compute_next_run(schedule)
    return out


async def _owned(db: AsyncSession, artifact_id: UUID, requester_id: UUID) -> Artifact | None:
    art = await db.get(Artifact, artifact_id)
    if art is None or art.owner_id != requester_id:
        return None
    return art


async def get(
    db: AsyncSession, artifact_id: UUID, requester_id: UUID
) -> ArtifactSchedule | None:
    if await _owned(db, artifact_id, requester_id) is None:
        return None
    stmt = select(ArtifactSchedule).where(ArtifactSchedule.artifact_id == artifact_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def upsert(
    db: AsyncSession,
    artifact_id: UUID,
    requester_id: UUID,
    *,
    cadence: ScheduleCadence,
    refresh_instruction: str,
    enabled: bool = True,
    completion_mode: ScheduleCompletion = ScheduleCompletion.RECURRING,
    end_at: datetime | None = None,
) -> ArtifactSchedule | None:
    art = await _owned(db, artifact_id, requester_id)
    if art is None:
        return None
    stmt = select(ArtifactSchedule).where(ArtifactSchedule.artifact_id == artifact_id)
    sched = (await db.execute(stmt)).scalar_one_or_none()
    if sched is None:
        sched = ArtifactSchedule(owner_id=art.owner_id, artifact_id=artifact_id)
        db.add(sched)
    sched.cadence = cadence
    sched.cron_expr = cron_for(cadence)
    sched.refresh_instruction = refresh_instruction
    sched.enabled = enabled
    sched.completion_mode = completion_mode
    sched.end_at = end_at
    # Eine Neueinrichtung/Änderung reaktiviert einen zuvor pausierten/beendeten Zeitplan.
    sched.status = ScheduleStatus.ACTIVE
    sched.fail_count = 0
    await db.commit()
    await db.refresh(sched)
    return sched


async def delete(db: AsyncSession, artifact_id: UUID, requester_id: UUID) -> bool:
    sched = await get(db, artifact_id, requester_id)
    if sched is None:
        return False
    await db.delete(sched)
    await db.commit()
    return True


async def resume(
    db: AsyncSession, artifact_id: UUID, requester_id: UUID
) -> ArtifactSchedule | None:
    sched = await get(db, artifact_id, requester_id)
    if sched is None:
        return None
    sched.status = ScheduleStatus.ACTIVE
    sched.fail_count = 0
    await db.commit()
    await db.refresh(sched)
    return sched


# Schritt 3: Der Agent kann im erzeugten HTML einen Marker hinterlassen, um die
# Instanz zeitgesteuert selbst zu aktualisieren:
#   <!-- SCHEDULE: daily | Aktualisiere die Wetterdaten -->
_SCHEDULE_DIRECTIVE_RE = re.compile(
    r"<!--\s*SCHEDULE:\s*(hourly|daily|weekly)\s*\|\s*(.+?)\s*-->",
    re.IGNORECASE | re.DOTALL,
)


def extract_schedule_directives(html: str) -> tuple[str, list[tuple[ScheduleCadence, str]]]:
    """Findet SCHEDULE-Marker im HTML und gibt (bereinigtes_HTML, [(cadence, instruction)]) zurück.

    Reine Funktion → direkt testbar. Der Marker wird aus dem HTML entfernt, damit er
    nicht beim Nutzer sichtbar ist und sich nicht über Läufe hinweg aufstaut.
    """
    directives: list[tuple[ScheduleCadence, str]] = []
    for m in _SCHEDULE_DIRECTIVE_RE.finditer(html or ""):
        instruction = m.group(2).strip()
        if instruction:
            directives.append((ScheduleCadence(m.group(1).lower()), instruction))
    clean = _SCHEDULE_DIRECTIVE_RE.sub("", html or "").strip()
    return clean, directives


async def set_from_agent(
    db: AsyncSession,
    artifact_id: UUID,
    *,
    cadence: ScheduleCadence,
    refresh_instruction: str,
) -> ArtifactSchedule | None:
    """Vom Agenten (Worker-Kontext, kein Mensch) gesetzter Zeitplan — Owner = Artefakt-Owner.

    Idempotent: existiert schon ein Zeitplan für die Instanz, wird er aktualisiert.
    """
    art = await db.get(Artifact, artifact_id)
    if art is None:
        return None
    stmt = select(ArtifactSchedule).where(ArtifactSchedule.artifact_id == artifact_id)
    sched = (await db.execute(stmt)).scalar_one_or_none()
    if sched is None:
        sched = ArtifactSchedule(owner_id=art.owner_id, artifact_id=artifact_id)
        db.add(sched)
    sched.cadence = cadence
    sched.cron_expr = cron_for(cadence)
    sched.refresh_instruction = refresh_instruction
    sched.enabled = True
    sched.completion_mode = ScheduleCompletion.RECURRING
    sched.status = ScheduleStatus.ACTIVE
    sched.fail_count = 0
    await db.commit()
    await db.refresh(sched)
    return sched
