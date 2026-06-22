import pytest
from datetime import UTC, datetime

from app.db.models import ArtifactJob, RunStatus
from app.db.session import SessionLocal
from app.services import artifact_jobs as jobs


def test_artifact_job_mode_defaults_to_update():
    j = ArtifactJob()
    # Default kommt aus dem Mapped-Column-default; ohne Flush ist er None,
    # daher den Spalten-Default prüfen:
    assert ArtifactJob.__table__.c.mode.default.arg == "update"


@pytest.mark.asyncio
async def test_create_job_from_tool_sets_mode():
    from uuid import uuid4
    from sqlalchemy import select
    from app.db.models import Agent, Artifact, User, Visibility, TemplateOutput

    async with SessionLocal() as db:
        u = User(email=f"m1-{uuid4()}@x.de", google_sub=str(uuid4()))
        db.add(u); await db.flush()
        a = Agent(owner_id=u.id, name="A", role="r")
        db.add(a); await db.flush()
        art = Artifact(owner_id=u.id, agent_id=a.id, title=f"art-{uuid4()}",
                       output_type=TemplateOutput("html"), visibility=Visibility.UNLISTED)
        db.add(art); await db.commit(); await db.refresh(art)

        job = await jobs.create_job_from_tool(
            db, artifact_id=art.id, owner_id=u.id, title="T",
            instruction="Begrüße", trigger_kind="recurring", cadence="hourly",
            mode="reminder",
        )
        assert job is not None and job.mode == "reminder"


def test_cron_for_presets():
    assert jobs.cron_for("hourly") == "0 * * * *"
    assert jobs.cron_for("daily") == "0 6 * * *"
    assert jobs.cron_for("weekly") == "0 6 * * 1"


def test_compute_next_run_recurring_uses_cron():
    j = ArtifactJob(
        trigger_kind="recurring",
        cron_expr="0 6 * * *",
        created_at=datetime(2026, 6, 10, 5, 0, tzinfo=UTC),
    )
    nxt = jobs.compute_next_run(j, now=datetime(2026, 6, 10, 5, 0, tzinfo=UTC))
    assert nxt == datetime(2026, 6, 10, 6, 0, tzinfo=UTC)


def test_compute_next_run_once_returns_run_at_then_none_after_run():
    when = datetime(2026, 6, 11, 8, 0, tzinfo=UTC)
    j = ArtifactJob(trigger_kind="once", run_at=when)
    assert jobs.compute_next_run(j) == when
    j.last_run_at = when  # schon gelaufen → kein weiterer Lauf
    assert jobs.compute_next_run(j) is None


def test_apply_run_outcome_autopause_after_three_failures():
    j = ArtifactJob(fail_count=0, status="active")
    jobs.apply_run_outcome(j, RunStatus.FAILED)
    jobs.apply_run_outcome(j, RunStatus.FAILED)
    assert j.status == "active" and j.fail_count == 2
    jobs.apply_run_outcome(j, RunStatus.COMPLETED)
    assert j.fail_count == 0
    jobs.apply_run_outcome(j, RunStatus.FAILED)
    jobs.apply_run_outcome(j, RunStatus.FAILED)
    jobs.apply_run_outcome(j, RunStatus.FAILED)
    assert j.status == "paused" and j.fail_count == 3


def test_is_transient_error_detects_platform_failures():
    # Plattform-/vorübergehende Fehler (nicht Schuld des Jobs):
    assert jobs.is_transient_error("Error code: 401 - invalid x-api-key")
    assert jobs.is_transient_error("authentication_error: bad key")
    assert jobs.is_transient_error("Guthaben aufgebraucht")
    assert jobs.is_transient_error("Error code: 429 rate_limit_error")
    assert jobs.is_transient_error("overloaded_error")
    # Echte/inhaltliche Fehler zählen weiter:
    assert not jobs.is_transient_error("ValueError: invalid name")
    assert not jobs.is_transient_error("")
    assert not jobs.is_transient_error(None)


def test_apply_run_outcome_transient_error_does_not_penalize():
    # Plattformfehler (ungültiger Key, leeres Guthaben) dürfen den Timer NICHT pausieren.
    j = ArtifactJob(fail_count=0, status="active")
    for _ in range(5):
        jobs.apply_run_outcome(j, RunStatus.FAILED, error="Error code: 401 - invalid x-api-key")
    assert j.status == "active" and j.fail_count == 0
    for _ in range(5):
        jobs.apply_run_outcome(j, RunStatus.FAILED, error="Guthaben aufgebraucht")
    assert j.status == "active" and j.fail_count == 0


def test_apply_run_outcome_real_failure_still_pauses():
    j = ArtifactJob(fail_count=0, status="active")
    for _ in range(3):
        jobs.apply_run_outcome(j, RunStatus.FAILED, error="ValueError: agent produced no output")
    assert j.status == "paused" and j.fail_count == 3


def test_to_out_includes_computed_next_run():
    from datetime import UTC, datetime
    from uuid import uuid4

    j = ArtifactJob(
        id=uuid4(),
        artifact_id=uuid4(),
        title="Täglich",
        instruction="aktualisiere",
        trigger_kind="recurring",
        cadence="daily",
        cron_expr="0 6 * * *",
        status="active",
        run_count=2,
        fail_count=0,
        created_at=datetime(2026, 6, 10, 5, 0, tzinfo=UTC),
    )
    out = jobs.to_out(j)
    assert out.title == "Täglich"
    assert out.status == "active"
    assert out.run_count == 2
    assert out.next_run_at is not None


async def _seed_owner_and_artifact(db, client):
    from sqlalchemy import select
    from uuid import UUID
    from app.db.models import User
    from app.services import artifacts as art_svc

    owner = (await db.execute(select(User))).scalars().first()
    # Echten Agenten anlegen: Artifact.agent_id ist ein FK auf agents.id.
    resp = await client.post("/agents", json={"name": "Seed-Agent"})
    assert resp.status_code == 201, resp.text
    agent_id = UUID(resp.json()["id"])
    art = await art_svc.create_instance(
        db, owner_id=owner.id, agent_id=agent_id, title="X", output_type="html"
    )
    return owner, art


@pytest.mark.asyncio
async def test_list_for_artifact_and_active_counts(client):
    # client-Fixture stellt sicher, dass mind. ein User existiert (AUTH_DISABLED_FOR_TESTS)
    await client.get("/artifacts")
    async with SessionLocal() as db:
        owner, art = await _seed_owner_and_artifact(db, client)
        db.add(ArtifactJob(
            artifact_id=art.id, owner_id=owner.id, title="A", instruction="x",
            trigger_kind="recurring", cadence="daily", cron_expr="0 6 * * *", status="active",
        ))
        db.add(ArtifactJob(
            artifact_id=art.id, owner_id=owner.id, title="B", instruction="y",
            trigger_kind="once", run_at=None, status="completed",
        ))
        await db.commit()

        out = await jobs.list_for_artifact(db, art.id, owner.id)
        assert out is not None and len(out) == 2
        counts = await jobs.active_counts(db, owner.id)
        # nur der aktive Job zählt
        assert counts.get(art.id) == 1
        # Fremder Nutzer darf nicht lesen
        from uuid import UUID as _UUID
        assert await jobs.list_for_artifact(db, art.id, _UUID(int=0)) is None


@pytest.mark.asyncio
async def test_tick_jobs_triggers_and_reschedules(client, tmp_path, monkeypatch):
    from datetime import UTC, datetime, timedelta
    from uuid import UUID

    from sqlalchemy import select

    from app.db.models import ArtifactJob, RunStatus, User, Work, WorkRun
    from app.services import artifacts as art_svc
    from app import cron_runner

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    # adjust nicht wirklich ausführen — nur prüfen, dass der Job getriggert/umgeplant wird.
    triggered: list = []

    a = await client.post(
        "/agents", json={"name": "P", "role": "x", "skills": ["a"], "visibility": "public"}
    )
    agent_id = UUID(a.json()["id"])
    async with SessionLocal() as db:
        owner = (await db.execute(select(User))).scalars().first()
        art = await art_svc.create_instance(
            db, owner_id=owner.id, agent_id=agent_id, title="T", output_type="html",
        )
        due = datetime.now(UTC) - timedelta(hours=1)
        job = ArtifactJob(
            artifact_id=art.id, owner_id=owner.id, title="due", instruction="go",
            trigger_kind="recurring", cadence="hourly", cron_expr="0 * * * *",
            status="active", created_at=due, notify_email=True,
        )
        db.add(job)
        await db.commit()
        job_id = job.id

    async def fake_adjust(db, artifact_id, owner_id, instruction, *, notify_owner=False, notify_chat=False, mode="update"):
        triggered.append((artifact_id, notify_owner))
        work = Work(owner_id=owner_id, title="T", goal="g")
        db.add(work)
        await db.flush()
        run = WorkRun(work_id=work.id, status=RunStatus.PENDING)
        db.add(run)
        await db.flush()
        return run.id

    monkeypatch.setattr("app.services.artifacts.adjust", fake_adjust)

    await cron_runner.tick_jobs()

    assert triggered and triggered[0][1] is True  # notify_owner aus notify_email
    async with SessionLocal() as db:
        j = await db.get(ArtifactJob, job_id)
        assert j.run_count == 1 and j.last_run_id is not None


@pytest.mark.asyncio
async def test_tick_jobs_once_completes(client, tmp_path, monkeypatch):
    from datetime import UTC, datetime, timedelta
    from uuid import UUID

    from sqlalchemy import select

    from app.db.models import ArtifactJob, RunStatus, User, Work, WorkRun
    from app.services import artifacts as art_svc
    from app import cron_runner

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    triggered: list = []

    a = await client.post(
        "/agents", json={"name": "P", "role": "x", "skills": ["a"], "visibility": "public"}
    )
    agent_id = UUID(a.json()["id"])
    async with SessionLocal() as db:
        owner = (await db.execute(select(User))).scalars().first()
        art = await art_svc.create_instance(
            db, owner_id=owner.id, agent_id=agent_id, title="Once", output_type="html",
        )
        due = datetime.now(UTC) - timedelta(hours=1)
        job = ArtifactJob(
            artifact_id=art.id, owner_id=owner.id, title="once", instruction="go",
            trigger_kind="once", run_at=due, status="active",
        )
        db.add(job)
        await db.commit()
        job_id = job.id

    async def fake_adjust(db, artifact_id, owner_id, instruction, *, notify_owner=False, notify_chat=False, mode="update"):
        triggered.append((artifact_id, notify_owner))
        work = Work(owner_id=owner_id, title="T", goal="g")
        db.add(work)
        await db.flush()
        run = WorkRun(work_id=work.id, status=RunStatus.PENDING)
        db.add(run)
        await db.flush()
        return run.id

    monkeypatch.setattr("app.services.artifacts.adjust", fake_adjust)

    await cron_runner.tick_jobs()

    assert any(t[0] == art.id for t in triggered)
    async with SessionLocal() as db:
        j = await db.get(ArtifactJob, job_id)
        assert j.status == "completed"
        assert j.run_count == 1
        assert j.last_run_id is not None


@pytest.mark.asyncio
async def test_tick_jobs_autopauses_after_failed_runs(client, tmp_path, monkeypatch):
    from datetime import UTC, datetime, timedelta
    from uuid import UUID

    from sqlalchemy import select

    from app.db.models import ArtifactJob, RunStatus, User, Work, WorkRun
    from app.services import artifacts as art_svc
    from app import cron_runner

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    triggered: list = []

    a = await client.post(
        "/agents", json={"name": "P", "role": "x", "skills": ["a"], "visibility": "public"}
    )
    agent_id = UUID(a.json()["id"])
    async with SessionLocal() as db:
        owner = (await db.execute(select(User))).scalars().first()
        art = await art_svc.create_instance(
            db, owner_id=owner.id, agent_id=agent_id, title="Fail", output_type="html",
        )
        # Vorlauf, der fehlgeschlagen ist.
        work = Work(owner_id=owner.id, title="T", goal="g")
        db.add(work)
        await db.flush()
        prev = WorkRun(work_id=work.id, status=RunStatus.FAILED)
        db.add(prev)
        await db.flush()
        due = datetime.now(UTC) - timedelta(hours=1)
        job = ArtifactJob(
            artifact_id=art.id, owner_id=owner.id, title="failing", instruction="go",
            trigger_kind="recurring", cadence="hourly", cron_expr="0 * * * *",
            status="active", created_at=due, fail_count=2, last_run_id=prev.id,
        )
        db.add(job)
        await db.commit()
        job_id = job.id
        art_id = art.id

    async def fake_adjust(db, artifact_id, owner_id, instruction, *, notify_owner=False, notify_chat=False, mode="update"):
        triggered.append((artifact_id, notify_owner))
        work = Work(owner_id=owner_id, title="T", goal="g")
        db.add(work)
        await db.flush()
        run = WorkRun(work_id=work.id, status=RunStatus.PENDING)
        db.add(run)
        await db.flush()
        return run.id

    monkeypatch.setattr("app.services.artifacts.adjust", fake_adjust)

    await cron_runner.tick_jobs()

    # Dritter Fehlschlag → pausiert, NICHT erneut getriggert.
    assert not any(t[0] == art_id for t in triggered)
    async with SessionLocal() as db:
        j = await db.get(ArtifactJob, job_id)
        assert j.status == "paused"
        assert j.fail_count == 3


@pytest.mark.asyncio
async def test_tick_jobs_skips_while_previous_run_pending(client, tmp_path, monkeypatch):
    from datetime import UTC, datetime, timedelta
    from uuid import UUID

    from sqlalchemy import select

    from app.db.models import ArtifactJob, RunStatus, User, Work, WorkRun
    from app.services import artifacts as art_svc
    from app import cron_runner

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    triggered: list = []

    a = await client.post(
        "/agents", json={"name": "P", "role": "x", "skills": ["a"], "visibility": "public"}
    )
    agent_id = UUID(a.json()["id"])
    async with SessionLocal() as db:
        owner = (await db.execute(select(User))).scalars().first()
        art = await art_svc.create_instance(
            db, owner_id=owner.id, agent_id=agent_id, title="Pending", output_type="html",
        )
        work = Work(owner_id=owner.id, title="T", goal="g")
        db.add(work)
        await db.flush()
        prev = WorkRun(work_id=work.id, status=RunStatus.PENDING)
        db.add(prev)
        await db.flush()
        due = datetime.now(UTC) - timedelta(hours=1)
        job = ArtifactJob(
            artifact_id=art.id, owner_id=owner.id, title="pending", instruction="go",
            trigger_kind="recurring", cadence="hourly", cron_expr="0 * * * *",
            status="active", created_at=due, run_count=1, last_run_id=prev.id,
        )
        db.add(job)
        await db.commit()
        job_id = job.id
        art_id = art.id

    async def fake_adjust(db, artifact_id, owner_id, instruction, *, notify_owner=False, notify_chat=False, mode="update"):
        triggered.append((artifact_id, notify_owner))
        work = Work(owner_id=owner_id, title="T", goal="g")
        db.add(work)
        await db.flush()
        run = WorkRun(work_id=work.id, status=RunStatus.PENDING)
        db.add(run)
        await db.flush()
        return run.id

    monkeypatch.setattr("app.services.artifacts.adjust", fake_adjust)

    await cron_runner.tick_jobs()

    # Vorlauf läuft noch → übersprungen, kein erneuter Trigger.
    assert not any(t[0] == art_id for t in triggered)
    async with SessionLocal() as db:
        j = await db.get(ArtifactJob, job_id)
        assert j.run_count == 1
        assert j.status == "active"


@pytest.mark.asyncio
async def test_upsert_from_agent_idempotent(client, tmp_path, monkeypatch):
    from uuid import UUID

    from sqlalchemy import select

    from app.db.models import ArtifactJob, User
    from app.services import artifacts as art_svc

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    a = await client.post(
        "/agents", json={"name": "P", "role": "x", "skills": ["a"], "visibility": "public"}
    )
    agent_id = UUID(a.json()["id"])
    async with SessionLocal() as db:
        owner = (await db.execute(select(User))).scalars().first()
        art = await art_svc.create_instance(
            db, owner_id=owner.id, agent_id=agent_id, title="UA", output_type="html",
        )
        await jobs.upsert_from_agent(db, art.id, cadence="daily", instruction="erste")
        await jobs.upsert_from_agent(db, art.id, cadence="hourly", instruction="zweite")
        rows = (await db.execute(
            select(ArtifactJob).where(ArtifactJob.artifact_id == art.id)
        )).scalars().all()
    assert len(rows) == 1  # idempotent: ein Auto-Job pro Instanz
    assert rows[0].cadence == "hourly" and rows[0].instruction == "zweite"
    assert rows[0].created_by == "agent"


@pytest.mark.asyncio
async def test_create_job_from_tool_and_cancel(client, tmp_path, monkeypatch):
    from uuid import UUID, uuid4

    from sqlalchemy import select

    from app.db.models import ArtifactJob, User
    from app.services import artifacts as art_svc

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    a = await client.post(
        "/agents", json={"name": "P", "role": "x", "skills": ["a"], "visibility": "public"}
    )
    agent_id = UUID(a.json()["id"])
    async with SessionLocal() as db:
        owner = (await db.execute(select(User))).scalars().first()
        art = await art_svc.create_instance(
            db, owner_id=owner.id, agent_id=agent_id, title="CJ", output_type="html",
        )
        job = await jobs.create_job_from_tool(
            db, artifact_id=art.id, owner_id=owner.id, title="Bus",
            instruction="check bus", trigger_kind="recurring",
            cadence="daily", cron_expr="0 6 * * *", notify_telegram=True,
        )
        assert job is not None and job.created_by == "agent" and job.status == "active"
        assert job.trigger_kind == "recurring" and job.cron_expr == "0 6 * * *"
        assert job.notify_telegram is True and job.notify_chat is True
        assert await jobs.create_job_from_tool(
            db, artifact_id=art.id, owner_id=uuid4(), title="x", instruction="y",
            trigger_kind="once",
        ) is None
        assert await jobs.cancel_job(db, job.id, owner.id) is True
        refreshed = await db.get(ArtifactJob, job.id)
        assert refreshed.status == "completed"
        assert await jobs.cancel_job(db, job.id, uuid4()) is False
