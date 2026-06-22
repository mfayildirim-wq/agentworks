from app.services import agent_tools as t


def test_is_safe_public_url_blocks_internal_and_bad_schemes():
    assert t.is_safe_public_url("http://8.8.8.8") is True          # öffentliche IP
    assert t.is_safe_public_url("https://8.8.8.8/pfad") is True
    assert t.is_safe_public_url("http://127.0.0.1") is False        # loopback
    assert t.is_safe_public_url("http://10.1.2.3") is False         # privat
    assert t.is_safe_public_url("http://169.254.169.254") is False  # link-local / metadata
    assert t.is_safe_public_url("http://[::1]/") is False           # ipv6 loopback
    assert t.is_safe_public_url("ftp://example.com") is False       # falsches schema
    assert t.is_safe_public_url("kein-url") is False


import pytest


def test_html_to_text_strips_tags_and_scripts():
    html = "<html><head><style>x{}</style></head><body><h1>Hallo</h1>" \
           "<script>evil()</script><p>Welt  hier</p></body></html>"
    out = t._html_to_text(html)
    assert "Hallo" in out and "Welt" in out
    assert "evil" not in out and "x{}" not in out
    assert "<" not in out


@pytest.mark.asyncio
async def test_web_fetch_rejects_internal_url_without_network():
    # SSRF-Guard greift VOR jedem Netzwerkzugriff → deterministisch, kein httpx nötig.
    out = await t.web_fetch("http://127.0.0.1:8000/secret")
    assert out.startswith("Fehler") and "erlaubt" in out


def test_format_search_results_top5():
    data = {"results": [
        {"title": "A", "url": "https://a.de", "content": "Inhalt A"},
        {"title": "B", "url": "https://b.de", "content": "Inhalt B"},
        {"title": "C", "url": "https://c.de", "content": ""},
        {"title": "D", "url": "https://d.de", "content": "D"},
        {"title": "E", "url": "https://e.de", "content": "E"},
        {"title": "F", "url": "https://f.de", "content": "F"},
    ]}
    out = t._format_search_results(data)
    assert "A — https://a.de — Inhalt A" in out
    assert out.count("\n") == 4  # genau 5 Zeilen (Top 5)
    assert "F —" not in out


def test_format_search_results_empty():
    assert t._format_search_results({"results": []}) == "Keine Treffer."


def test_provider_supports_tools():
    from agent_runtime.model_client import provider_supports_tools

    assert provider_supports_tools("anthropic") is True
    assert provider_supports_tools("openai") is True
    assert provider_supports_tools("ollama") is False
    assert provider_supports_tools("") is False


def test_tool_capability_note():
    assert t.tool_capability_note(True) == ""
    note = t.tool_capability_note(False)
    assert "Online-Modell" in note and "erfinde keine" in note.lower()


def test_build_tools_returns_web_tools():
    from uuid import uuid4

    tools = t.build_tools(artifact_id=uuid4(), owner_id=uuid4(), allow_scheduling=False)
    names = {fn.__name__ for fn in tools}
    assert names == {"web_search", "web_fetch"}


def test_executor_context_carries_tools():
    from agent_runtime.executor import ExecutorContext

    ctx = ExecutorContext(api_key="k", on_event=lambda _e: None, tools=[t.web_search])
    assert ctx.tools == [t.web_search]
    # Default ist eine leere Liste (kein geteilter State).
    ctx2 = ExecutorContext(api_key="k", on_event=lambda _e: None)
    assert ctx2.tools == []


@pytest.mark.asyncio
async def test_web_fetch_caps_oversized_body(monkeypatch):
    import httpx
    from app.services import agent_tools as at

    # Riesiger Body (> _MAX_BYTES) von einem "öffentlichen" Host.
    big = "<p>" + ("A" * (at._MAX_BYTES + 500_000)) + "</p>"

    def handler(request):
        return httpx.Response(200, headers={"content-type": "text/html"}, text=big)

    real_client = httpx.AsyncClient

    def fake_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        kwargs.pop("follow_redirects", None)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(at.httpx, "AsyncClient", fake_client)
    out = await at.web_fetch("http://8.8.8.8/big")
    # Ergebnis ist gekürzt (<= 8000 sichtbare Zeichen) und kein Fehler.
    assert not out.startswith("Fehler")
    assert len(out) <= 8000


from datetime import UTC, datetime


def test_cron_from_local_daily_summer_and_winter():
    summer = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)  # Europe/Berlin = UTC+2
    winter = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)  # Europe/Berlin = UTC+1
    assert t.cron_from_local("daily", 8, "Europe/Berlin", ref=summer) == "0 6 * * *"
    assert t.cron_from_local("daily", 8, "Europe/Berlin", ref=winter) == "0 7 * * *"


def test_cron_from_local_hourly_and_weekly():
    summer = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
    assert t.cron_from_local("hourly", 8, "Europe/Berlin", ref=summer) == "0 * * * *"
    assert t.cron_from_local("weekly", 8, "Europe/Berlin", ref=summer) == "0 6 * * 1"


def test_run_at_from_local_converts_to_utc():
    out = t.run_at_from_local("2026-06-15T08:00", "Europe/Berlin")
    assert out == datetime(2026, 6, 15, 6, 0, tzinfo=UTC)


def test_cron_from_local_with_minute():
    summer = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)  # Europe/Berlin = UTC+2
    assert t.cron_from_local("daily", 21, "Europe/Berlin", minute=15, ref=summer) == "15 19 * * *"
    assert t.cron_from_local("weekly", 8, "Europe/Berlin", minute=30, ref=summer) == "30 6 * * 1"
    assert t.cron_from_local("hourly", 0, "Europe/Berlin", minute=30, ref=summer) == "30 * * * *"
    # Default minute=0 bleibt rückwärtskompatibel
    assert t.cron_from_local("daily", 8, "Europe/Berlin", ref=summer) == "0 6 * * *"


def test_scheduling_etiquette_requires_consent():
    note = t.scheduling_etiquette()
    assert "schedule_job" in note
    assert "zugestimmt" in note or "frage" in note.lower()


def test_slot_etiquette_demands_distinct_slots():
    note = t.slot_etiquette()
    low = note.lower()
    # Muss die "ein Slot pro Thema/Objekt"-Anweisung enthalten (kein Sammel-Slot).
    assert "ein slot pro" in low or "eigenen slot" in low


def test_build_tools_with_scheduling_has_five():
    from uuid import uuid4

    tools = t.build_tools(artifact_id=uuid4(), owner_id=uuid4(), allow_scheduling=True)
    names = {fn.__name__ for fn in tools}
    assert names == {"web_search", "web_fetch", "schedule_job", "list_jobs", "cancel_job"}


@pytest.mark.asyncio
async def test_schedule_job_tool_creates_recurring_job(client, tmp_path, monkeypatch):
    from uuid import UUID

    from sqlalchemy import select

    from app.db.models import ArtifactJob, User
    from app.db.session import SessionLocal
    from app.services import artifacts as art_svc

    monkeypatch.setattr(art_svc.settings, "media_root", str(tmp_path))
    a = await client.post(
        "/agents", json={"name": "P", "role": "x", "skills": ["a"], "visibility": "public"}
    )
    agent_id = UUID(a.json()["id"])
    async with SessionLocal() as db:
        owner = (await db.execute(select(User))).scalars().first()
        art = await art_svc.create_instance(
            db, owner_id=owner.id, agent_id=agent_id, title="ST", output_type="html",
        )
        owner_id, art_id = owner.id, art.id

    tools = t.build_tools(artifact_id=art_id, owner_id=owner_id, allow_scheduling=True)
    schedule_job = next(fn for fn in tools if fn.__name__ == "schedule_job")
    msg = await schedule_job(
        title="Busplan", instruction="prüfe Busse", trigger_kind="recurring",
        cadence="daily", hour=8,
    )
    assert "angelegt" in msg

    async with SessionLocal() as db:
        rows = (await db.execute(
            select(ArtifactJob).where(ArtifactJob.artifact_id == art_id)
        )).scalars().all()
    assert len(rows) == 1
    assert rows[0].trigger_kind == "recurring" and rows[0].cadence == "daily"
    assert rows[0].cron_expr and rows[0].title == "Busplan"


def test_slot_etiquette_mentions_action_buttons():
    text = t.slot_etiquette()
    assert "data-action" in text


from app.db.session import SessionLocal


def test_scheduling_etiquette_explains_modes_and_chips():
    from app.services.agent_tools import scheduling_etiquette
    e = scheduling_etiquette()
    assert "reminder" in e and "update" in e
    # Bei Unklarheit per Chips nachfragen:
    assert "chips" in e.lower()


@pytest.mark.asyncio
async def test_schedule_job_tool_sets_reminder_mode():
    from uuid import uuid4
    from app.db.models import Agent, Artifact, User, Visibility, TemplateOutput
    from app.services import agent_tools
    from app.services import artifact_jobs as jobs

    async with SessionLocal() as db:
        u = User(email=f"m2-{uuid4()}@x.de", google_sub=str(uuid4()))
        db.add(u); await db.flush()
        a = Agent(owner_id=u.id, name="A", role="r")
        db.add(a); await db.flush()
        art = Artifact(owner_id=u.id, agent_id=a.id, title=f"art-{uuid4()}",
                       output_type=TemplateOutput("html"), visibility=Visibility.UNLISTED)
        db.add(art); await db.commit(); await db.refresh(art)
        art_id, owner_id = art.id, u.id

    schedule_job, _list, _cancel = agent_tools._scheduling_tools(art_id, owner_id)
    msg = await schedule_job(title="Gruß", instruction="Begrüße", trigger_kind="recurring",
                             cadence="hourly", mode="reminder")
    assert "angelegt" in msg

    async with SessionLocal() as db:
        rows = await jobs.list_for_artifact(db, art_id, owner_id)
        assert rows and any(getattr(j, "title", "") == "Gruß" for j in rows)
        # mode am ORM prüfen:
        from sqlalchemy import select
        from app.db.models import ArtifactJob
        j = (await db.execute(select(ArtifactJob).where(ArtifactJob.artifact_id == art_id))).scalars().first()
        assert j.mode == "reminder"
