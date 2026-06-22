from uuid import UUID

import pytest
from sqlalchemy import select, text

from app.db.session import SessionLocal


@pytest.mark.asyncio
async def test_backfill_maps_schedule_to_job(client, tmp_path, monkeypatch):
    from app.db.models import ArtifactJob, ArtifactSchedule, ScheduleCadence, ScheduleCompletion, User
    from app.services import artifact_jobs as jobs
    from app.services import artifacts as art_svc

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    a = await client.post(
        "/agents", json={"name": "P", "role": "x", "skills": ["a"], "visibility": "public"}
    )
    agent_id = UUID(a.json()["id"])
    async with SessionLocal() as db:
        owner = (await db.execute(select(User))).scalars().first()
        art = await art_svc.create_instance(
            db, owner_id=owner.id, agent_id=agent_id, title="BF", output_type="html",
        )
        db.add(ArtifactSchedule(
            owner_id=owner.id, artifact_id=art.id, cadence=ScheduleCadence.DAILY,
            cron_expr="0 6 * * *", refresh_instruction="aktualisiere",
            completion_mode=ScheduleCompletion.RECURRING, run_count=2,
        ))
        await db.commit()

        await db.execute(text(jobs.BACKFILL_SCHEDULES_SQL))
        await db.commit()

        rows = (await db.execute(
            select(ArtifactJob).where(ArtifactJob.artifact_id == art.id)
        )).scalars().all()
    assert len(rows) == 1
    j = rows[0]
    assert j.trigger_kind == "recurring"
    assert j.cadence == "daily"
    assert j.cron_expr == "0 6 * * *"
    assert j.instruction == "aktualisiere"
    assert j.run_count == 2
    assert j.created_by == "system"
    assert j.notify_email is True and j.notify_telegram is True and j.notify_chat is False
