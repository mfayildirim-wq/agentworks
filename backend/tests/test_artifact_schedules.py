from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from app.db.session import SessionLocal


async def _agent(client):
    a = await client.post(
        "/agents", json={"name": "Planner", "role": "x", "skills": ["a"], "visibility": "public"}
    )
    return a.json()["id"]


async def _owner(db):
    from sqlalchemy import select

    from app.db.models import User

    return (await db.execute(select(User))).scalars().first()


async def _artifact(db, owner_id, agent_id):
    from app.services import artifacts as art_svc

    art = await art_svc.create_instance(
        db, owner_id=owner_id, agent_id=agent_id, title="Reiseplan", output_type="html",
    )
    await art_svc.record_version(
        db, artifact_id=art.id, content="<h1>v1</h1>", prompt="", run_id=None
    )
    return art


def test_cron_for_presets():
    from app.db.models import ScheduleCadence
    from app.services import artifact_schedules as sched

    assert sched.cron_for(ScheduleCadence.HOURLY) == "0 * * * *"
    assert sched.cron_for(ScheduleCadence.DAILY) == "0 6 * * *"
    assert sched.cron_for(ScheduleCadence.WEEKLY) == "0 6 * * 1"


def test_apply_run_outcome_autopause_after_three_failures():
    from app.db.models import ArtifactSchedule, RunStatus, ScheduleStatus
    from app.services import artifact_schedules as sched

    s = ArtifactSchedule(fail_count=0, status=ScheduleStatus.ACTIVE)
    sched.apply_run_outcome(s, RunStatus.FAILED)
    sched.apply_run_outcome(s, RunStatus.FAILED)
    assert s.status == ScheduleStatus.ACTIVE and s.fail_count == 2
    # ein Erfolg dazwischen setzt den Zähler zurück
    sched.apply_run_outcome(s, RunStatus.COMPLETED)
    assert s.fail_count == 0
    # drei Fehler in Folge → Auto-Pause
    sched.apply_run_outcome(s, RunStatus.FAILED)
    sched.apply_run_outcome(s, RunStatus.FAILED)
    sched.apply_run_outcome(s, RunStatus.FAILED)
    assert s.status == ScheduleStatus.PAUSED and s.fail_count == 3


@pytest.mark.asyncio
async def test_upsert_creates_then_updates(client, tmp_path, monkeypatch):
    from app.db.models import ScheduleCadence
    from app.services import artifact_schedules as sched
    from app.services import artifacts as art_svc

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    agent_id = await _agent(client)
    async with SessionLocal() as db:
        owner = await _owner(db)
        art = await _artifact(db, owner.id, UUID(agent_id))

        s1 = await sched.upsert(
            db, art.id, owner.id,
            cadence=ScheduleCadence.DAILY, refresh_instruction="Aktualisiere Wetter", enabled=True,
        )
        assert s1 is not None
        assert s1.cron_expr == "0 6 * * *"
        first_id = s1.id

        # zweiter Aufruf aktualisiert dieselbe Zeile (UNIQUE pro Artefakt)
        s2 = await sched.upsert(
            db, art.id, owner.id,
            cadence=ScheduleCadence.HOURLY, refresh_instruction="Stündlich", enabled=False,
        )
        assert s2.id == first_id
        assert s2.cron_expr == "0 * * * *"
        assert s2.refresh_instruction == "Stündlich"
        assert s2.enabled is False


@pytest.mark.asyncio
async def test_upsert_rejects_foreign_owner(client, tmp_path, monkeypatch):
    from uuid import uuid4

    from app.db.models import ScheduleCadence
    from app.services import artifact_schedules as sched
    from app.services import artifacts as art_svc

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    agent_id = await _agent(client)
    async with SessionLocal() as db:
        owner = await _owner(db)
        art = await _artifact(db, owner.id, UUID(agent_id))
        assert await sched.upsert(
            db, art.id, uuid4(),
            cadence=ScheduleCadence.DAILY, refresh_instruction="x", enabled=True,
        ) is None


@pytest.mark.asyncio
async def test_resume_resets_status_and_failcount(client, tmp_path, monkeypatch):
    from app.db.models import ScheduleCadence, ScheduleStatus
    from app.services import artifact_schedules as sched
    from app.services import artifacts as art_svc

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    agent_id = await _agent(client)
    async with SessionLocal() as db:
        owner = await _owner(db)
        art = await _artifact(db, owner.id, UUID(agent_id))
        s = await sched.upsert(
            db, art.id, owner.id,
            cadence=ScheduleCadence.DAILY, refresh_instruction="x", enabled=True,
        )
        s.status = ScheduleStatus.PAUSED
        s.fail_count = 3
        await db.commit()

        resumed = await sched.resume(db, art.id, owner.id)
        assert resumed.status == ScheduleStatus.ACTIVE
        assert resumed.fail_count == 0


@pytest.mark.asyncio
async def test_schedule_api_roundtrip(client, tmp_path, monkeypatch):
    from app.services import artifacts as art_svc

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    agent_id = await _agent(client)
    async with SessionLocal() as db:
        owner = await _owner(db)
        art = await _artifact(db, owner.id, UUID(agent_id))
        artifact_id = str(art.id)

    # zuerst kein Zeitplan
    g0 = await client.get(f"/artifacts/{artifact_id}/schedule")
    assert g0.status_code == 200
    assert g0.json() is None

    # anlegen
    put = await client.put(
        f"/artifacts/{artifact_id}/schedule",
        json={"cadence": "daily", "refresh_instruction": "Aktualisiere Wetter", "enabled": True},
    )
    assert put.status_code == 200, put.text
    body = put.json()
    assert body["cron_expr"] == "0 6 * * *"
    assert body["next_run_at"]

    # lesen
    g1 = await client.get(f"/artifacts/{artifact_id}/schedule")
    assert g1.json()["refresh_instruction"] == "Aktualisiere Wetter"

    # leere Anweisung wird abgelehnt
    bad = await client.put(
        f"/artifacts/{artifact_id}/schedule",
        json={"cadence": "daily", "refresh_instruction": "", "enabled": True},
    )
    assert bad.status_code == 422

    # löschen
    d = await client.delete(f"/artifacts/{artifact_id}/schedule")
    assert d.status_code == 204
    assert (await client.get(f"/artifacts/{artifact_id}/schedule")).json() is None


def test_extract_schedule_directives_parses_and_strips():
    from app.db.models import ScheduleCadence
    from app.services import artifact_schedules as sched

    html = (
        "<html><body><h1>Plan</h1>"
        "<!-- SCHEDULE: daily | Aktualisiere die Wetterdaten -->"
        "</body></html>"
    )
    clean, directives = sched.extract_schedule_directives(html)
    assert directives == [(ScheduleCadence.DAILY, "Aktualisiere die Wetterdaten")]
    assert "SCHEDULE" not in clean  # Marker entfernt
    assert "<h1>Plan</h1>" in clean

    # Kein Marker -> leer, HTML unveraendert
    clean2, d2 = sched.extract_schedule_directives("<p>x</p>")
    assert d2 == []
    assert clean2 == "<p>x</p>"


@pytest.mark.asyncio
async def test_set_from_agent_creates_recurring_schedule(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.artifacts.settings.media_root", str(tmp_path))
    from app.db.models import ScheduleCadence, ScheduleCompletion, ScheduleStatus
    from app.services import artifact_schedules as sched

    agent_id = await _agent(client)
    async with SessionLocal() as db:
        owner = await _owner(db)
        art = await _artifact(db, owner.id, UUID(agent_id))
        s = await sched.set_from_agent(
            db, art.id, cadence=ScheduleCadence.WEEKLY, refresh_instruction="Wochenupdate"
        )
        assert s is not None
        assert s.cadence == ScheduleCadence.WEEKLY
        assert s.refresh_instruction == "Wochenupdate"
        assert s.completion_mode == ScheduleCompletion.RECURRING
        assert s.status == ScheduleStatus.ACTIVE
        assert s.enabled is True
