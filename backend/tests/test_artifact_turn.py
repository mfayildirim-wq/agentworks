"""Tests für den Dialog-Turn: Chat-Prosa → Nachricht, Canvas-Block → neue Version."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.db.models import ArtifactMessage, ArtifactVersion, User
from app.db.session import SessionLocal
from app.services import artifacts as art_svc
from app.services.artifact_chat import run_turn


async def _setup_artifact(client, *, with_message: bool = True) -> UUID:
    a = await client.post(
        "/agents",
        json={"name": "Planner", "role": "Reiseplaner", "skills": ["x"], "visibility": "public"},
    )
    agent_id = UUID(a.json()["id"])
    async with SessionLocal() as db:
        owner = (await db.execute(select(User))).scalars().first()
        art = await art_svc.create_instance(
            db, owner_id=owner.id, agent_id=agent_id, title="Travel", output_type="html"
        )
        if with_message:
            db.add(ArtifactMessage(artifact_id=art.id, role="user", content="London, 3 Tage"))
        await db.commit()
        return art.id


@pytest.mark.asyncio
async def test_question_only_writes_chat_message_no_version(client):
    art_id = await _setup_artifact(client)

    async def complete(system: str, message: str) -> str:
        return "Wohin genau und an welchen Tagen?"

    async with SessionLocal() as db:
        msg = await run_turn(db, artifact_id=art_id, complete=complete)
        assert msg is not None
        assert msg.role == "assistant"
        assert msg.content == "Wohin genau und an welchen Tagen?"
        assert msg.version_id is None
        art = await db.get(art_svc.Artifact, art_id)
        assert art.current_version_id is None


@pytest.mark.asyncio
async def test_canvas_block_creates_version_and_links_message(client):
    art_id = await _setup_artifact(client)

    async def complete(system: str, message: str) -> str:
        return "Hier ist dein erster Plan:\n```canvas\n<h1>London</h1>\n```"

    async with SessionLocal() as db:
        msg = await run_turn(db, artifact_id=art_id, complete=complete)
        assert msg is not None
        assert "Hier ist dein erster Plan" in msg.content
        assert msg.version_id is not None
        version = await db.get(ArtifactVersion, msg.version_id)
        assert "<h1>London</h1>" in version.content


@pytest.mark.asyncio
async def test_canvas_only_uses_default_confirmation_text(client):
    art_id = await _setup_artifact(client)

    async def complete(system: str, message: str) -> str:
        return "```canvas\n<h1>Nur Seite</h1>\n```"

    async with SessionLocal() as db:
        msg = await run_turn(db, artifact_id=art_id, complete=complete)
        assert msg.version_id is not None
        assert msg.content.strip() != ""  # generische Bestätigung statt leer


@pytest.mark.asyncio
async def test_system_prompt_receives_purpose_and_history(client):
    art_id = await _setup_artifact(client)
    captured = {}

    async def complete(system: str, message: str) -> str:
        captured["system"] = system
        captured["message"] = message
        return "ok"

    async with SessionLocal() as db:
        await run_turn(db, artifact_id=art_id, complete=complete)

    assert "Reiseplaner" in captured["system"]  # Zweck/Scope im System-Prompt
    assert "canvas" in captured["system"].lower()  # Canvas-Vertrag erklärt
    assert "London, 3 Tage" in captured["message"]  # Chatverlauf im Turn-Text


@pytest.mark.asyncio
async def test_chat_endpoint_stores_message_and_lists_it(client, monkeypatch):
    import app.workers as workers

    monkeypatch.setattr(workers.execute_chat_turn, "send", lambda *a, **k: None)
    art_id = await _setup_artifact(client)

    # _setup_artifact legt bereits eine User-Nachricht an; jetzt eine weitere via API.
    r = await client.post(f"/artifacts/{art_id}/chat", json={"message": "Mehr zu Museen"})
    assert r.status_code == 202

    r2 = await client.get(f"/artifacts/{art_id}/messages")
    assert r2.status_code == 200
    msgs = r2.json()
    assert [m["content"] for m in msgs] == ["London, 3 Tage", "Mehr zu Museen"]
    assert all(m["role"] == "user" for m in msgs)


@pytest.mark.asyncio
async def test_messages_include_version_no_after_canvas_turn(client, monkeypatch):
    import app.workers as workers

    monkeypatch.setattr(workers.execute_chat_turn, "send", lambda *a, **k: None)
    art_id = await _setup_artifact(client)

    async def complete(system: str, message: str) -> str:
        return "Plan steht:\n```canvas\n<h1>London</h1>\n```"

    async with SessionLocal() as db:
        await run_turn(db, artifact_id=art_id, complete=complete)

    r = await client.get(f"/artifacts/{art_id}/messages")
    msgs = r.json()
    assistant = [m for m in msgs if m["role"] == "assistant"][0]
    assert assistant["version_no"] == 1


@pytest.mark.asyncio
async def test_chat_unknown_artifact_is_404(client, monkeypatch):
    import app.workers as workers

    monkeypatch.setattr(workers.execute_chat_turn, "send", lambda *a, **k: None)
    r = await client.post(f"/artifacts/{uuid4()}/chat", json={"message": "x"})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_init_turn_uses_kickoff_when_no_history(client):
    art_id = await _setup_artifact(client, with_message=False)
    captured = {}

    async def complete(system: str, message: str) -> str:
        captured["message"] = message
        return "Hallo! Wohin soll es gehen?"

    async with SessionLocal() as db:
        msg = await run_turn(db, artifact_id=art_id, complete=complete)

    assert "Neue Sitzung" in captured["message"]  # Kickoff statt leerem Verlauf
    assert msg.role == "assistant"


@pytest.mark.asyncio
async def test_start_turn_enqueues_only_when_empty(client, monkeypatch):
    import app.workers as workers
    from app.services import artifact_chat as chat_svc

    sent: list = []
    monkeypatch.setattr(workers.execute_chat_turn, "send", lambda *a, **k: sent.append(a))

    art_id = await _setup_artifact(client, with_message=False)
    async with SessionLocal() as db:
        owner = (await db.execute(select(User))).scalars().first()
        assert await chat_svc.start_turn(db, art_id, owner.id) is True
    assert len(sent) == 1  # leerer Verlauf → ein Init-Turn

    # Bei vorhandenem Verlauf kein weiterer Init-Turn.
    async with SessionLocal() as db:
        db.add(ArtifactMessage(artifact_id=art_id, role="assistant", content="hi"))
        await db.commit()
        owner = (await db.execute(select(User))).scalars().first()
        assert await chat_svc.start_turn(db, art_id, owner.id) is True
    assert len(sent) == 1  # unverändert
