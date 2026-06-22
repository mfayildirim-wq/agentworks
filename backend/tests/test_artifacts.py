from uuid import UUID, uuid4

import pytest

from app.db.session import SessionLocal


async def _user_and_agent(client):
    a = await client.post(
        "/agents", json={"name": "Planner", "role": "x", "skills": ["a"], "visibility": "public"}
    )
    return a.json()["id"]


async def _owner(db):
    from sqlalchemy import select

    from app.db.models import User

    return (await db.execute(select(User))).scalars().first()


@pytest.mark.asyncio
async def test_record_version_creates_versions_and_file(client, tmp_path, monkeypatch):
    from app.services import artifacts as art_svc

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    agent_id = await _user_and_agent(client)

    async with SessionLocal() as db:
        owner = await _owner(db)
        art = await art_svc.create_instance(
            db,
            owner_id=owner.id,
            agent_id=UUID(agent_id),
            title="Reiseplan",
            output_type="html",
            inputs={"ziel": "Rom"},
        )
        v1 = await art_svc.record_version(
            db, artifact_id=art.id, content="<h1>v1</h1>", prompt="erstelle", run_id=None
        )
        assert v1.version_no == 1
        v2 = await art_svc.record_version(
            db, artifact_id=art.id, content="<h1>v2</h1>", prompt="mehr", run_id=None
        )
        assert v2.version_no == 2

        view = await art_svc.get_view(db, art.id, owner)
        assert view is not None
        assert view.id == art.id
        assert view.inputs == {"ziel": "Rom"}
        assert view.current_content == "<h1>v2</h1>"
        assert view.current_version_no == 2
        assert len(view.versions) == 2
        art_id = art.id

    # Datei wird unter der Artefakt-id (nicht der agent-id) abgelegt
    f = tmp_path / "artifacts" / str(owner.id) / f"{art_id}.html"
    assert f.exists()
    assert f.read_text() == "<h1>v2</h1>"


@pytest.mark.asyncio
async def test_record_version_stores_data(client, tmp_path, monkeypatch):
    from app.services import artifacts as art_svc

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    agent_id = await _user_and_agent(client)

    async with SessionLocal() as db:
        owner = await _owner(db)
        art = await art_svc.create_instance(
            db,
            owner_id=owner.id,
            agent_id=UUID(agent_id),
            title="Slot-DB Instanz",
            output_type="html",
        )
        v = await art_svc.record_version(
            db,
            artifact_id=art.id,
            content="<p>x</p>",
            prompt="",
            run_id=None,
            data={"layout": "sections", "slots": []},
        )
        assert v.data == {"layout": "sections", "slots": []}


@pytest.mark.asyncio
async def test_two_instances_same_agent_are_independent(client, tmp_path, monkeypatch):
    from app.services import artifacts as art_svc

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    agent_id = await _user_and_agent(client)

    async with SessionLocal() as db:
        owner = await _owner(db)
        a = await art_svc.create_instance(
            db, owner_id=owner.id, agent_id=UUID(agent_id),
            title="Reiseplaner - Istanbul", output_type="html", inputs={"ziel": "Istanbul"},
        )
        b = await art_svc.create_instance(
            db, owner_id=owner.id, agent_id=UUID(agent_id),
            title="Reiseplaner - London", output_type="html", inputs={"ziel": "London"},
        )
        assert a.id != b.id

        await art_svc.record_version(
            db, artifact_id=a.id, content="<h1>Istanbul</h1>", prompt="", run_id=None
        )
        await art_svc.record_version(
            db, artifact_id=b.id, content="<h1>London</h1>", prompt="", run_id=None
        )

        va = await art_svc.get_view(db, a.id, owner)
        vb = await art_svc.get_view(db, b.id, owner)
        assert va.current_content == "<h1>Istanbul</h1>"
        assert vb.current_content == "<h1>London</h1>"
        # getrennte Versionshistorie: je genau eine Version
        assert len(va.versions) == 1 and len(vb.versions) == 1
        a_id, b_id = a.id, b.id

    # getrennte Dateien
    base = tmp_path / "artifacts" / str(owner.id)
    assert (base / f"{a_id}.html").read_text() == "<h1>Istanbul</h1>"
    assert (base / f"{b_id}.html").read_text() == "<h1>London</h1>"


@pytest.mark.asyncio
async def test_public_html_respects_visibility(client, tmp_path, monkeypatch):
    from app.services import artifacts as art_svc

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    agent_id = await _user_and_agent(client)
    async with SessionLocal() as db:
        from app.db.models import Artifact, Visibility

        owner = await _owner(db)
        art = await art_svc.create_instance(
            db, owner_id=owner.id, agent_id=UUID(agent_id), title="T", output_type="html",
        )
        await art_svc.record_version(
            db, artifact_id=art.id, content="<h1>hi</h1>", prompt="", run_id=None
        )
        # neue Instanzen sind per Default privat → explizit auf unlisted setzen für öffentlichen Abruf
        art_pub = await db.get(Artifact, art.id)
        art_pub.visibility = Visibility.UNLISTED
        await db.commit()
        # unlisted → öffentlich abrufbar
        assert await art_svc.public_html(db, art.id) == "<h1>hi</h1>"
        # auf private setzen → 404 (None)
        art_orm = await db.get(Artifact, art.id)
        art_orm.visibility = Visibility.PRIVATE
        await db.commit()
        assert await art_svc.public_html(db, art.id) is None


@pytest.mark.asyncio
async def test_worker_records_artifact_version_after_loop_run(client, tmp_path, monkeypatch):
    import app.workers as workers
    from app.services import artifacts as art_svc

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    monkeypatch.setattr(workers.execute_run, "send", lambda *a, **k: None)

    agent_id = await _user_and_agent(client)
    t = await client.post(
        "/templates",
        json={
            "title": "Reiseplaner",
            "visibility": "public",
            "output_type": "html",
            "config": {"agent_ids": [agent_id], "prompt_template": "Plane {{x}}."},
            "input_schema": [{"key": "x", "label": "X", "type": "string", "required": True}],
        },
    )
    tid = t.json()["id"]
    inst = await client.post(f"/templates/{tid}/instantiate", json={"inputs": {"x": "Rom"}})
    body = inst.json()
    artifact_id = body["artifact_id"]
    assert artifact_id

    # Instanziieren startet keinen Lauf mehr — den Loop-Run liefert der adjust-Pfad.
    from sqlalchemy import select

    from app.db.models import User

    async with SessionLocal() as db:
        owner = (await db.execute(select(User))).scalars().first()
        run_id = str(await art_svc.adjust(db, UUID(artifact_id), owner.id, "Plane Rom."))

    from agent_runtime.executor import ExecutorResult

    class _FakeExec:
        async def run(self, work, ctx):
            return ExecutorResult(
                final_message="<h1>Rom</h1>",
                total_tokens_in=1,
                total_tokens_out=1,
                total_cost_usd=0.0,
                metadata={"artifact": "<h1>Rom</h1>", "output_type": "html",
                          "iterations": 1, "stop_reason": "done"},
            )

    monkeypatch.setattr(workers, "create_executor", lambda mode: _FakeExec())
    import agent_runtime.executors.goal_loop as gl

    monkeypatch.setattr(gl, "GoalLoopExecutor", lambda: _FakeExec())

    await workers._execute_run_async(UUID(run_id))

    async with SessionLocal() as db:
        owner = await _owner(db)
        view = await art_svc.get_view(db, UUID(artifact_id), owner)
        assert view is not None
        assert view.current_content == "<h1>Rom</h1>"
        assert view.current_version_no == 1


@pytest.mark.asyncio
async def test_adjust_creates_run_with_current_html_context(client, tmp_path, monkeypatch):
    import app.workers as workers
    from app.services import artifacts as art_svc

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    monkeypatch.setattr(workers.execute_run, "send", lambda *a, **k: None)

    agent_id = await _user_and_agent(client)
    async with SessionLocal() as db:
        owner = await _owner(db)
        art = await art_svc.create_instance(
            db, owner_id=owner.id, agent_id=UUID(agent_id), title="Reiseplan", output_type="html",
        )
        await art_svc.record_version(
            db, artifact_id=art.id, content="<h1>v1</h1>", prompt="erst", run_id=None
        )
        owner_id = owner.id
        artifact_id = art.id

    async with SessionLocal() as db:
        run_id = await art_svc.adjust(db, artifact_id, owner_id, "Füge ein Hotel hinzu.")
        assert run_id is not None

        from app.db.models import Work, WorkRun

        wr = await db.get(WorkRun, run_id)
        work = await db.get(Work, wr.work_id)
        assert "Füge ein Hotel hinzu." in work.goal
        assert "<h1>v1</h1>" in work.initial_message
        assert work.loop_config and work.loop_config["enabled"] is True
        # Der Adjust-Run schreibt zurück in genau diese Instanz
        assert work.loop_config["artifact_id"] == str(artifact_id)


@pytest.mark.asyncio
async def test_adjust_rejects_foreign_artifact(client, tmp_path, monkeypatch):
    from app.services import artifacts as art_svc

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    agent_id = await _user_and_agent(client)
    async with SessionLocal() as db:
        owner = await _owner(db)
        art = await art_svc.create_instance(
            db, owner_id=owner.id, agent_id=UUID(agent_id), title="T", output_type="html",
        )
        # fremde requester_id → kein Run
        assert await art_svc.adjust(db, art.id, uuid4(), "x") is None
        # unbekannte artifact_id → kein Run
        assert await art_svc.adjust(db, uuid4(), owner.id, "x") is None


@pytest.mark.asyncio
async def test_public_page_endpoint_serves_html_with_csp(client, tmp_path, monkeypatch):
    from app.services import artifacts as art_svc

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    agent_id = await _user_and_agent(client)
    async with SessionLocal() as db:
        owner = await _owner(db)
        art = await art_svc.create_instance(
            db, owner_id=owner.id, agent_id=UUID(agent_id), title="T", output_type="html",
        )
        await art_svc.record_version(
            db, artifact_id=art.id, content="<h1>Seite</h1>", prompt="", run_id=None
        )
        # neue Instanzen sind per Default privat → explizit öffentlich machen
        from app.db.models import Artifact, Visibility

        art_pub = await db.get(Artifact, art.id)
        art_pub.visibility = Visibility.UNLISTED
        await db.commit()
        artifact_id = str(art.id)

    r = await client.get(f"/p/{artifact_id}")
    assert r.status_code == 200
    assert "Seite" in r.text
    assert "script-src 'none'" in r.headers.get("content-security-policy", "")
    # unbekannte id → 404
    assert (await client.get(f"/p/{uuid4()}")).status_code == 404

    # Metadaten-API
    m = await client.get(f"/artifacts/{artifact_id}")
    assert m.status_code == 200
    assert m.json()["current_version_no"] == 1

    # eigene Liste enthält die Instanz mit id
    mine = await client.get("/artifacts")
    assert mine.status_code == 200
    assert any(a["id"] == artifact_id for a in mine.json())


@pytest.mark.asyncio
async def test_artifact_failure_does_not_break_run_finalization(client, tmp_path, monkeypatch):
    from agent_runtime.executor import ExecutorResult

    import app.workers as workers
    from app.services import artifacts as art_svc

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    monkeypatch.setattr(workers.execute_run, "send", lambda *a, **k: None)

    agent_id = await _user_and_agent(client)
    t = await client.post(
        "/templates",
        json={
            "title": "T",
            "visibility": "public",
            "output_type": "html",
            "config": {"agent_ids": [agent_id], "prompt_template": "Plane {{x}}."},
            "input_schema": [{"key": "x", "label": "X", "type": "string", "required": True}],
        },
    )
    tid = t.json()["id"]
    inst = await client.post(f"/templates/{tid}/instantiate", json={"inputs": {"x": "Rom"}})
    artifact_id = inst.json()["artifact_id"]

    # Instanziieren startet keinen Lauf mehr — den Loop-Run liefert der adjust-Pfad.
    from sqlalchemy import select

    from app.db.models import User

    async with SessionLocal() as db:
        owner = (await db.execute(select(User))).scalars().first()
        run_id = str(await art_svc.adjust(db, UUID(artifact_id), owner.id, "Plane Rom."))

    class _FakeExec:
        async def run(self, work, ctx):
            return ExecutorResult(
                final_message="<h1>x</h1>", total_tokens_in=1, total_tokens_out=1,
                total_cost_usd=0.0,
                metadata={"artifact": "<h1>x</h1>", "output_type": "html",
                          "iterations": 1, "stop_reason": "done"},
            )

    monkeypatch.setattr(workers, "create_executor", lambda mode: _FakeExec())
    import agent_runtime.executors.goal_loop as gl

    monkeypatch.setattr(gl, "GoalLoopExecutor", lambda: _FakeExec())

    async def _boom(*a, **k):
        raise RuntimeError("disk full")

    monkeypatch.setattr(art_svc, "record_version", _boom)

    await workers._execute_run_async(UUID(run_id))

    async with SessionLocal() as db:
        from app.db.models import RunStatus, WorkRun

        run = await db.get(WorkRun, UUID(run_id))
        assert run.status == RunStatus.COMPLETED
        assert run.finished_at is not None


def test_build_scope_guard():
    """Guardrail-Text bindet an den Zweck und verlangt Ablehnung von Off-Topic."""
    from app.services.artifacts import build_scope_guard

    g = build_scope_guard("Reiseplanung: Reiseplan erstellen und anpassen.")
    assert "Reiseplanung: Reiseplan erstellen und anpassen." in g
    assert "Guardrail" in g
    assert "lehnst du höflich ab" in g
    assert g.endswith("\n\n")

    # Leerer Zweck -> sinnvoller Fallback, kein Crash.
    fallback = build_scope_guard("")
    assert "die im Template definierte Aufgabe" in fallback


@pytest.mark.asyncio
async def test_list_mine_has_recent_actions_and_job_count(client, tmp_path, monkeypatch):
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
            db, owner_id=owner.id, agent_id=agent_id, title="L", output_type="html",
        )
        await art_svc.record_version(
            db, artifact_id=art.id, content="<h1>v1</h1>", prompt="erste Aktion", run_id=None
        )
        db.add(ArtifactJob(
            artifact_id=art.id, owner_id=owner.id, title="J", instruction="z",
            trigger_kind="recurring", cadence="daily", cron_expr="0 6 * * *", status="active",
        ))
        await db.commit()
        items = await art_svc.list_mine(db, owner)
    mine = next(i for i in items if i.title == "L")
    assert mine.job_count == 1
    assert mine.recent_actions and mine.recent_actions[0].prompt == "erste Aktion"
    assert mine.schedule_cadence == "daily"  # Badge jetzt aus aktivem Job


@pytest.mark.asyncio
async def test_adjust_threads_notify_chat_into_loop_config(client, tmp_path, monkeypatch):
    import app.workers as workers
    from uuid import UUID

    from sqlalchemy import select

    from app.db.models import User, Work
    from app.services import artifacts as art_svc

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    monkeypatch.setattr(workers.execute_run, "send", lambda *a, **k: None)

    agent_id = await _user_and_agent(client)
    async with SessionLocal() as db:
        owner = (await db.execute(select(User))).scalars().first()
        art = await art_svc.create_instance(
            db, owner_id=owner.id, agent_id=UUID(agent_id), title="NC", output_type="html",
        )
        run_id = await art_svc.adjust(
            db, art.id, owner.id, "tu was", notify_owner=True, notify_chat=True
        )
        run = await db.get(workers.WorkRun, run_id)
        work = await db.get(Work, run.work_id)
    assert work.loop_config.get("notify_chat") is True
    assert work.loop_config.get("notify_owner") is True


@pytest.mark.asyncio
async def test_worker_injects_web_tools_for_instance_run(client, tmp_path, monkeypatch):
    import app.workers as workers
    from uuid import UUID

    from sqlalchemy import select

    from agent_runtime.executor import ExecutorResult
    from app.db.models import User
    from app.services import artifacts as art_svc

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    monkeypatch.setattr(workers.execute_run, "send", lambda *a, **k: None)

    agent_id = await _user_and_agent(client)
    async with SessionLocal() as db:
        owner = (await db.execute(select(User))).scalars().first()
        art = await art_svc.create_instance(
            db, owner_id=owner.id, agent_id=UUID(agent_id), title="TI", output_type="html",
        )
        run_id = str(await art_svc.adjust(db, art.id, owner.id, "tu was"))

    seen: list[str] = []

    class _FakeExec:
        async def run(self, work, ctx):
            seen.extend(fn.__name__ for fn in (ctx.tools or []))
            return ExecutorResult(
                final_message="<h1>x</h1>", total_tokens_in=1, total_tokens_out=1,
                total_cost_usd=0.0,
                metadata={"artifact": "<h1>x</h1>", "output_type": "html",
                          "iterations": 1, "stop_reason": "done"},
            )

    monkeypatch.setattr(workers, "create_executor", lambda mode: _FakeExec())
    import agent_runtime.executors.goal_loop as gl

    monkeypatch.setattr(gl, "GoalLoopExecutor", lambda: _FakeExec())

    await workers._execute_run_async(UUID(run_id))

    assert "web_search" in seen and "web_fetch" in seen
    assert "schedule_job" not in seen  # automatische Läufe planen keine Jobs


@pytest.mark.asyncio
async def test_worker_posts_chat_message_on_notify_chat(client, tmp_path, monkeypatch):
    import app.workers as workers
    from uuid import UUID

    from sqlalchemy import select

    from agent_runtime.executor import ExecutorResult
    from app.db.models import ArtifactMessage, User
    from app.services import artifacts as art_svc

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    monkeypatch.setattr(workers.execute_run, "send", lambda *a, **k: None)

    agent_id = await _user_and_agent(client)
    async with SessionLocal() as db:
        owner = (await db.execute(select(User))).scalars().first()
        art = await art_svc.create_instance(
            db, owner_id=owner.id, agent_id=UUID(agent_id), title="CHATNOTIFY",
            output_type="html",
        )
        art_id = art.id
        run_id = str(
            await art_svc.adjust(db, art.id, owner.id, "tu was", notify_chat=True)
        )

    class _FakeExec:
        async def run(self, work, ctx):
            return ExecutorResult(
                final_message="<h1>neu</h1>", total_tokens_in=1, total_tokens_out=1,
                total_cost_usd=0.0,
                metadata={"artifact": "<h1>neu</h1>", "output_type": "html",
                          "iterations": 1, "stop_reason": "done"},
            )

    monkeypatch.setattr(workers, "create_executor", lambda mode: _FakeExec())
    import agent_runtime.executors.goal_loop as gl

    monkeypatch.setattr(gl, "GoalLoopExecutor", lambda: _FakeExec())

    await workers._execute_run_async(UUID(run_id))

    async with SessionLocal() as db:
        msgs = (await db.execute(
            select(ArtifactMessage).where(
                ArtifactMessage.artifact_id == art_id,
                ArtifactMessage.role == "assistant",
            )
        )).scalars().all()
    assert any(m.version_id is not None and "Aktualisierung" in m.content for m in msgs)


@pytest.mark.asyncio
async def test_connection_put_get_hides_secret(client, monkeypatch):
    import app.workers as workers
    monkeypatch.setattr(workers.execute_chat_turn, "send", lambda *a, **k: None)
    r = await client.post("/agents", json={"name": "Conn"})
    aid = r.json()["id"]
    from app.db.session import SessionLocal
    from app.services import artifacts as art_svc
    from sqlalchemy import select
    from app.db.models import User
    from uuid import UUID
    async with SessionLocal() as db:
        owner = (await db.execute(select(User))).scalars().first()
        art = await art_svc.create_instance(db, owner_id=owner.id, agent_id=UUID(aid), title="X", output_type="html")
        art_id = str(art.id)
    put = await client.put(f"/artifacts/{art_id}/connections/wordpress", json={
        "config": {"site_url": "https://x.example", "username": "u"}, "secret": "apppw",
    })
    assert put.status_code == 200, put.text
    body = put.json()
    assert body["kind"] == "wordpress" and body["configured"] is True
    assert body["config"]["site_url"] == "https://x.example"
    assert "secret" not in body
    lst = await client.get(f"/artifacts/{art_id}/connections")
    assert lst.status_code == 200
    items = lst.json()
    assert any(i["kind"] == "wordpress" and "secret" not in i for i in items)


@pytest.mark.asyncio
async def test_put_connection_rejects_unknown_kind(client):
    r = await client.post("/agents", json={"name": "Conn2"})
    aid = r.json()["id"]
    from app.db.session import SessionLocal
    from app.services import artifacts as art_svc
    from sqlalchemy import select
    from app.db.models import User
    from uuid import UUID
    async with SessionLocal() as db:
        owner = (await db.execute(select(User))).scalars().first()
        art = await art_svc.create_instance(db, owner_id=owner.id, agent_id=UUID(aid), title="X", output_type="html")
        art_id = str(art.id)
    bad = await client.put(f"/artifacts/{art_id}/connections/dropbox", json={"config": {}, "secret": "x"})
    assert bad.status_code == 400


@pytest.mark.asyncio
async def test_put_mcp_connection_ok(client):
    r = await client.post("/agents", json={"name": "McpConn"})
    aid = r.json()["id"]
    from app.db.session import SessionLocal
    from app.services import artifacts as art_svc
    from app.services import mcp_catalog
    from sqlalchemy import select
    from app.db.models import User
    from uuid import UUID
    async with SessionLocal() as db:
        await mcp_catalog.create(
            db, server_id="notion-conn", name="Notion", description="d",
            transport="http", url="https://mcp.example", requires_credential=True,
            updated_by=None, auth_header="Authorization",
            auth_value_template="Bearer {secret}", secret_label="T",
        )
        owner = (await db.execute(select(User))).scalars().first()
        art = await art_svc.create_instance(
            db, owner_id=owner.id, agent_id=UUID(aid), title="X", output_type="html"
        )
        art_id = str(art.id)
    put = await client.put(
        f"/artifacts/{art_id}/connections/mcp:notion-conn",
        json={"config": {}, "secret": "tok-xyz"},
    )
    assert put.status_code == 200, put.text
    body = put.json()
    assert body["kind"] == "mcp:notion-conn"
    assert "tok-xyz" not in put.text


@pytest.mark.asyncio
async def test_put_mcp_connection_rejects_credential_free(client):
    r = await client.post("/agents", json={"name": "McpFree"})
    aid = r.json()["id"]
    from app.db.session import SessionLocal
    from app.services import artifacts as art_svc
    from app.services import mcp_catalog
    from sqlalchemy import select
    from app.db.models import User
    from uuid import UUID
    async with SessionLocal() as db:
        await mcp_catalog.create(
            db, server_id="demo-free", name="DemoFree", description="d",
            transport="http", url="https://mcp.example", requires_credential=False,
            updated_by=None,
        )
        owner = (await db.execute(select(User))).scalars().first()
        art = await art_svc.create_instance(
            db, owner_id=owner.id, agent_id=UUID(aid), title="X", output_type="html"
        )
        art_id = str(art.id)
    bad = await client.put(
        f"/artifacts/{art_id}/connections/mcp:demo-free",
        json={"config": {}, "secret": "x"},
    )
    assert bad.status_code == 400


@pytest.mark.asyncio
async def test_put_mcp_connection_rejects_unknown(client):
    r = await client.post("/agents", json={"name": "McpGhost"})
    aid = r.json()["id"]
    from app.db.session import SessionLocal
    from app.services import artifacts as art_svc
    from sqlalchemy import select
    from app.db.models import User
    from uuid import UUID
    async with SessionLocal() as db:
        owner = (await db.execute(select(User))).scalars().first()
        art = await art_svc.create_instance(
            db, owner_id=owner.id, agent_id=UUID(aid), title="X", output_type="html"
        )
        art_id = str(art.id)
    bad = await client.put(
        f"/artifacts/{art_id}/connections/mcp:ghost-xyz",
        json={"config": {}, "secret": "x"},
    )
    assert bad.status_code == 400


@pytest.mark.asyncio
async def test_get_view_surfaces_mcp_credentials(client, tmp_path, monkeypatch):
    from app.db.models import Template, TemplateOutput, User, Visibility
    from app.services import artifact_connections, artifacts as art_svc, mcp_catalog
    from sqlalchemy import select

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    agent_id = await _user_and_agent(client)

    async with SessionLocal() as db:
        # credential-pflichtiger MCP-Server im Katalog
        await mcp_catalog.create(
            db, server_id="notion-view", name="Notion", description="",
            transport="streamable_http", url="https://x/mcp", requires_credential=True,
            updated_by="goa", auth_header="Authorization",
            auth_value_template="Bearer {secret}", secret_label="Notion-Token",
        )
        # ein credential-freier Server darf NICHT auftauchen
        await mcp_catalog.create(
            db, server_id="demo-view-free", name="DemoFree", description="",
            transport="http", url="https://x/mcp", requires_credential=False,
            updated_by="goa",
        )
        owner = (await db.execute(select(User))).scalars().first()
        tpl = Template(
            owner_id=owner.id,
            title="Mcp-Vorlage",
            visibility=Visibility.PUBLIC,
            output_type=TemplateOutput("html"),
            config={"mcp_servers": ["notion-view", "demo-view-free"]},
            input_schema=[],
        )
        db.add(tpl)
        await db.commit()
        await db.refresh(tpl)

        art = await art_svc.create_instance(
            db, owner_id=owner.id, agent_id=UUID(agent_id), title="X",
            output_type="html", template_id=tpl.id,
        )

        view = await art_svc.get_view(db, art.id, owner)
        assert view is not None
        assert len(view.mcp_credentials) == 1
        need = view.mcp_credentials[0]
        assert need.server_id == "notion-view"
        assert need.secret_label == "Notion-Token"
        assert need.configured is False

        await artifact_connections.upsert_connection(
            db, art.id, art.owner_id, kind="mcp:notion-view", config={}, secret="tok",
        )
        view2 = await art_svc.get_view(db, art.id, owner)
        assert len(view2.mcp_credentials) == 1
        assert view2.mcp_credentials[0].configured is True


@pytest.mark.asyncio
async def test_get_view_content_mode(client, tmp_path, monkeypatch):
    from app.db.models import Template, TemplateOutput, User, Visibility
    from app.services import artifacts as art_svc
    from sqlalchemy import select

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    agent_id = await _user_and_agent(client)

    async with SessionLocal() as db:
        owner = (await db.execute(select(User))).scalars().first()

        # Template mit content_mode="slots"
        tpl_slots = Template(
            owner_id=owner.id,
            title="Slots-Vorlage",
            visibility=Visibility.PUBLIC,
            output_type=TemplateOutput("html"),
            config={"content_mode": "slots"},
            input_schema=[],
        )
        # Default-Template (kein content_mode in config -> "html")
        tpl_html = Template(
            owner_id=owner.id,
            title="Html-Vorlage",
            visibility=Visibility.PUBLIC,
            output_type=TemplateOutput("html"),
            config={},
            input_schema=[],
        )
        db.add(tpl_slots)
        db.add(tpl_html)
        await db.commit()
        await db.refresh(tpl_slots)
        await db.refresh(tpl_html)

        art_slots = await art_svc.create_instance(
            db, owner_id=owner.id, agent_id=UUID(agent_id), title="S",
            output_type="html", template_id=tpl_slots.id,
        )
        art_html = await art_svc.create_instance(
            db, owner_id=owner.id, agent_id=UUID(agent_id), title="H",
            output_type="html", template_id=tpl_html.id,
        )

        view_slots = await art_svc.get_view(db, art_slots.id, owner)
        assert view_slots is not None
        assert view_slots.content_mode == "slots"

        view_html = await art_svc.get_view(db, art_html.id, owner)
        assert view_html is not None
        assert view_html.content_mode == "html"


@pytest.mark.asyncio
async def test_get_view_html_template_id(client, tmp_path, monkeypatch):
    from app.db.models import Template, TemplateOutput, User, Visibility
    from app.services import artifacts as art_svc
    from sqlalchemy import select

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    agent_id = await _user_and_agent(client)

    async with SessionLocal() as db:
        owner = (await db.execute(select(User))).scalars().first()

        # Template mit html_template_id="cards"
        tpl_cards = Template(
            owner_id=owner.id,
            title="Cards-Vorlage",
            visibility=Visibility.PUBLIC,
            output_type=TemplateOutput("html"),
            config={"html_template_id": "cards"},
            input_schema=[],
        )
        # Default-Template (kein html_template_id in config -> "")
        tpl_default = Template(
            owner_id=owner.id,
            title="Default-Vorlage",
            visibility=Visibility.PUBLIC,
            output_type=TemplateOutput("html"),
            config={},
            input_schema=[],
        )
        db.add(tpl_cards)
        db.add(tpl_default)
        await db.commit()
        await db.refresh(tpl_cards)
        await db.refresh(tpl_default)

        art_cards = await art_svc.create_instance(
            db, owner_id=owner.id, agent_id=UUID(agent_id), title="C",
            output_type="html", template_id=tpl_cards.id,
        )
        art_default = await art_svc.create_instance(
            db, owner_id=owner.id, agent_id=UUID(agent_id), title="D",
            output_type="html", template_id=tpl_default.id,
        )

        view_cards = await art_svc.get_view(db, art_cards.id, owner)
        assert view_cards is not None
        assert view_cards.html_template_id == "cards"

        view_default = await art_svc.get_view(db, art_default.id, owner)
        assert view_default is not None
        assert view_default.html_template_id == ""


@pytest.mark.asyncio
async def test_publish_endpoint_reports_message(client, monkeypatch):
    from app.services import sftp_publish
    async def fake_pub(db, aid, oid):
        return True, "Veröffentlicht: h/p"
    monkeypatch.setattr(sftp_publish, "publish_artifact", fake_pub)
    r = await client.post("/agents", json={"name": "Pub2"})
    aid = r.json()["id"]
    from app.db.session import SessionLocal
    from app.services import artifacts as art_svc
    from sqlalchemy import select
    from app.db.models import User
    from uuid import UUID
    async with SessionLocal() as db:
        owner = (await db.execute(select(User))).scalars().first()
        art = await art_svc.create_instance(db, owner_id=owner.id, agent_id=UUID(aid), title="X", output_type="html")
        art_id = str(art.id)
    res = await client.post(f"/artifacts/{art_id}/publish")
    assert res.status_code == 200 and res.json() == {"ok": True, "message": "Veröffentlicht: h/p"}


@pytest.mark.asyncio
async def test_slot_crud_owner_only(client):
    r = await client.post("/agents", json={"name": "Slots"})
    aid_agent = r.json()["id"]
    from app.db.session import SessionLocal
    from app.services import artifacts as art_svc
    from sqlalchemy import select
    from app.db.models import User
    from uuid import UUID
    async with SessionLocal() as db:
        owner = (await db.execute(select(User))).scalars().first()
        art = await art_svc.create_instance(
            db, owner_id=owner.id, agent_id=UUID(aid_agent), title="SlotInst", output_type="html"
        )
        aid = str(art.id)

    put = await client.put(f"/artifacts/{aid}/slots/a", json={"title": "Alpha", "body": "<p>A</p>"})
    assert put.status_code == 200, put.text
    assert any(s["id"] == "a" for s in put.json()["slots"])

    got = await client.get(f"/artifacts/{aid}/slots")
    assert got.status_code == 200, got.text
    body = got.json()
    assert any(s["id"] == "a" for s in body["slots"])
    assert "layout" in body

    lay = await client.put(f"/artifacts/{aid}/layout", json={"layout": "tabs"})
    assert lay.status_code == 200, lay.text
    assert lay.json()["layout"] == "tabs"

    bad = await client.put(f"/artifacts/{aid}/layout", json={"layout": "nope"})
    assert bad.status_code == 400, bad.text

    delr = await client.delete(f"/artifacts/{aid}/slots/a")
    assert delr.status_code == 200, delr.text
    assert not any(s["id"] == "a" for s in delr.json()["slots"])

    putb = await client.put(
        f"/artifacts/{aid}/slots/b", json={"body": "<p>ok</p><script>x()</script>"}
    )
    assert putb.status_code == 200, putb.text
    slot_b = next(s for s in putb.json()["slots"] if s["id"] == "b")
    assert "<script" not in slot_b["body"]


def test_build_adjust_initial_reminder_is_text_not_page():
    from app.services.artifacts import build_adjust_initial
    r = build_adjust_initial("reminder", "Begrüßungen senden", "<h1>alt</h1>", "Begrüße den Nutzer")
    assert "REINEN TEXT" in r
    assert "Begrüße den Nutzer" in r
    assert "KOMPLETTE" not in r            # keine Seiten-Anweisung
    assert "<h1>alt</h1>" not in r          # alte Seite nicht nötig
    # KEIN Scope-Guard im Reminder: der Agent darf die Zustellung nicht als off-topic ablehnen
    assert "Dafür ist dieser Agent nicht gedacht" not in r
    assert "KEINE Ablehnung" in r


def test_build_adjust_initial_update_is_page():
    from app.services.artifacts import build_adjust_initial
    u = build_adjust_initial("update", "Reiseplan", "<h1>alt</h1>", "Aktualisiere Wetter")
    assert "KOMPLETTE" in u
    assert "<h1>alt</h1>" in u
    assert "Aktualisiere Wetter" in u


@pytest.mark.asyncio
async def test_adjust_reminder_sets_job_mode_and_single_iteration(client, tmp_path, monkeypatch):
    from uuid import UUID
    from sqlalchemy import select
    import app.workers as workers
    from app.services import artifacts as art_svc
    from app.db.models import User, Work, WorkRun

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    monkeypatch.setattr(workers.execute_run, "send", lambda *a, **k: None)

    agent_id = await _user_and_agent(client)
    t = await client.post("/templates", json={
        "title": "T", "visibility": "public", "output_type": "html",
        "config": {"agent_ids": [agent_id], "prompt_template": "Plane {{x}}."},
        "input_schema": [{"key": "x", "label": "X", "type": "string", "required": True}]})
    tid = t.json()["id"]
    inst = await client.post(f"/templates/{tid}/instantiate", json={"inputs": {"x": "Rom"}})
    artifact_id = inst.json()["artifact_id"]

    async with SessionLocal() as db:
        owner = (await db.execute(select(User))).scalars().first()
        run_id = await art_svc.adjust(db, UUID(artifact_id), owner.id, "Begrüße", mode="reminder")

    async with SessionLocal() as db:
        run = await db.get(WorkRun, run_id)
        work = await db.get(Work, run.work_id)
        assert work.loop_config["job_mode"] == "reminder"
        assert work.loop_config["max_iterations"] == 1


@pytest.mark.asyncio
async def test_worker_reminder_posts_message_without_version(client, tmp_path, monkeypatch):
    from uuid import UUID
    from sqlalchemy import select, func
    from agent_runtime.executor import ExecutorResult
    import app.workers as workers
    from app.services import artifacts as art_svc
    from app.db.models import User, ArtifactMessage, ArtifactVersion

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    monkeypatch.setattr(workers.execute_run, "send", lambda *a, **k: None)

    agent_id = await _user_and_agent(client)
    t = await client.post("/templates", json={
        "title": "T", "visibility": "public", "output_type": "html",
        "config": {"agent_ids": [agent_id], "prompt_template": "Plane {{x}}."},
        "input_schema": [{"key": "x", "label": "X", "type": "string", "required": True}]})
    tid = t.json()["id"]
    inst = await client.post(f"/templates/{tid}/instantiate", json={"inputs": {"x": "Rom"}})
    artifact_id = UUID(inst.json()["artifact_id"])

    async with SessionLocal() as db:
        owner = (await db.execute(select(User))).scalars().first()
        before = (await db.execute(select(func.count()).select_from(ArtifactVersion)
                                   .where(ArtifactVersion.artifact_id == artifact_id))).scalar()
        run_id = await art_svc.adjust(db, artifact_id, owner.id, "Begrüße",
                                      notify_owner=True, notify_chat=True, mode="reminder")

    class _FakeExec:
        async def run(self, work, ctx):
            return ExecutorResult(
                final_message="Hallo 👋, schön dich zu sehen!",
                total_tokens_in=1, total_tokens_out=1, total_cost_usd=0.0,
                metadata={"output_type": "html", "iterations": 1, "stop_reason": "done"})

    monkeypatch.setattr(workers, "create_executor", lambda mode: _FakeExec())
    import agent_runtime.executors.goal_loop as gl
    monkeypatch.setattr(gl, "GoalLoopExecutor", lambda: _FakeExec())

    calls = []
    async def _fake_notify(user, subject, text, url):
        calls.append((subject, text)); return 1
    monkeypatch.setattr("app.services.notify.dispatch.notify_user", _fake_notify)

    await workers._execute_run_async(run_id)

    async with SessionLocal() as db:
        # KEINE neue Version
        after = (await db.execute(select(func.count()).select_from(ArtifactVersion)
                                  .where(ArtifactVersion.artifact_id == artifact_id))).scalar()
        assert after == before
        # Nachricht im Chat = der Agenten-Text
        msgs = (await db.execute(select(ArtifactMessage).where(
            ArtifactMessage.artifact_id == artifact_id,
            ArtifactMessage.role == "assistant"))).scalars().all()
        assert any("Hallo 👋" in (m.content or "") for m in msgs)
    # Email/Telegram-Versand (gemockt) wurde mit dem Text aufgerufen
    assert calls and "Hallo 👋" in calls[0][1]


def test_artifact_chat_summary_defaults():
    from app.db.models import Artifact
    assert Artifact.__table__.c.chat_summary.default.arg == ""
    assert Artifact.__table__.c.summarized_count.default.arg == 0
