"""Tests für den Ausgabe-Vertrag des Dialog-Agenten: Chat-Prosa vs. Canvas-HTML."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.services.artifact_chat import split_agent_output


def test_prose_only_is_chat_no_canvas():
    text = "Wohin soll die Reise gehen und wann ungefähr?"
    chat, canvas = split_agent_output(text)
    assert chat == "Wohin soll die Reise gehen und wann ungefähr?"
    assert canvas is None


def test_canvas_block_extracted_and_prose_kept():
    text = (
        "Klar, hier ist dein erster Reiseplan:\n\n"
        "```canvas\n<!doctype html><h1>London</h1>\n```\n\n"
        "Sag Bescheid, wenn ich etwas ergänzen soll."
    )
    chat, canvas = split_agent_output(text)
    assert canvas == "<!doctype html><h1>London</h1>"
    assert "Klar, hier ist dein erster Reiseplan:" in chat
    assert "Sag Bescheid" in chat
    assert "```" not in chat
    assert "<!doctype html>" not in chat


def test_html_fence_is_accepted_as_canvas():
    text = "Fertig:\n```html\n<p>Hallo</p>\n```"
    chat, canvas = split_agent_output(text)
    assert canvas == "<p>Hallo</p>"
    assert chat == "Fertig:"


def test_canvas_only_yields_empty_chat():
    text = "```canvas\n<h1>Nur Seite</h1>\n```"
    chat, canvas = split_agent_output(text)
    assert canvas == "<h1>Nur Seite</h1>"
    assert chat == ""


def test_raw_html_without_fence_is_treated_as_canvas():
    text = "<!doctype html>\n<html><body><h1>Plan</h1></body></html>"
    chat, canvas = split_agent_output(text)
    assert canvas is not None
    assert "<h1>Plan</h1>" in canvas
    assert chat == ""


def test_only_first_canvas_block_is_used():
    text = "A\n```canvas\n<h1>1</h1>\n```\nB\n```canvas\n<h1>2</h1>\n```"
    chat, canvas = split_agent_output(text)
    assert canvas == "<h1>1</h1>"


def test_unclosed_canvas_fence_is_treated_as_canvas():
    # Abgeschnittene Ausgabe (Zaun nie geschlossen): trotzdem als Canvas, nicht in den Chat.
    text = "Hier ist dein Plan:\n```canvas\n<!doctype html><h1>Istanbul</h1><p>unvollst"
    chat, canvas = split_agent_output(text)
    assert canvas is not None
    assert canvas.lstrip().startswith("<!doctype")
    assert "<h1>Istanbul</h1>" in canvas
    assert chat == "Hier ist dein Plan:"
    assert "```" not in chat


def test_status_lines_are_stripped_from_chat():
    # Altlast aus dem Loop-Protokoll: STATUS-Zeilen gehören nicht in den Chat.
    text = "Ich lege los!\nSTATUS: DONE"
    chat, canvas = split_agent_output(text)
    assert chat == "Ich lege los!"
    assert "STATUS" not in chat


def test_turn_system_prompt_mentions_chips_html_and_slots():
    from app.services.artifact_chat import build_turn_system_prompt

    assert "chips" in build_turn_system_prompt("p", None)
    assert "chips" in build_turn_system_prompt("p", None, content_mode="slots")


def test_chips_block_stays_in_chat_text():
    chat, canvas = split_agent_output("Hier:\n```chips\nJa\nNein\n```")
    assert "```chips" in chat and "Ja" in chat
    assert canvas is None


def test_prepared_slot_note_names_keys_and_forbids_other_slots():
    from app.services.artifact_chat import prepared_slot_note

    note = prepared_slot_note(
        [{"key": "title", "label": "Titel"}, {"key": "intro", "label": "Einleitung"}]
    )
    assert "title" in note
    assert "intro" in note
    assert "update_slot" in note
    assert "keine anderen" in note.lower() or "keine anderen Slots" in note


def test_prepared_slot_note_empty_for_no_placeholders():
    from app.services.artifact_chat import prepared_slot_note

    assert prepared_slot_note([]) == ""


@pytest.mark.asyncio
async def test_run_turn_summarizes_on_overflow(client):
    from uuid import UUID
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.db.models import User, Artifact, ArtifactMessage
    from app.services import artifact_chat
    from app.services import artifacts as art_svc

    await client.get("/artifacts")
    async with SessionLocal() as db:
        owner = (await db.execute(
            select(User).where(User.google_sub == "test-user"))).scalars().first()
        resp = await client.post("/agents", json={"name": "Sum-Agent"})
        agent_id = UUID(resp.json()["id"])
        art = await art_svc.create_instance(
            db, owner_id=owner.id, agent_id=agent_id, title=f"Sum-{uuid4()}",
            output_type="html")
        # 20 Nachrichten anlegen
        for i in range(20):
            db.add(ArtifactMessage(artifact_id=art.id,
                role="user" if i % 2 == 0 else "assistant", content=f"nachricht-{i}"))
        await db.commit()
        art_id = art.id

    captured = {}
    async def fake_complete(system, message):
        captured["message"] = message
        return "ok"
    async def fake_summarize(prev, to_fold):
        return "ZUSAMMENGEFASST"

    async with SessionLocal() as db:
        await artifact_chat.run_turn(db, artifact_id=art_id,
            complete=fake_complete, summarize=fake_summarize)

    async with SessionLocal() as db:
        art = await db.get(Artifact, art_id)
        assert art.chat_summary == "ZUSAMMENGEFASST"
        assert art.summarized_count == 14          # 20 - keep_recent(6)
    # Der LLM-Input enthält die Zusammenfassung, aber NICHT die ältesten Nachrichten
    assert "ZUSAMMENGEFASST" in captured["message"]
    assert "nachricht-0" not in captured["message"]
    assert "nachricht-19" in captured["message"]    # jüngste wörtlich


@pytest.mark.asyncio
async def test_run_turn_no_summarize_below_buffer(client):
    from uuid import UUID
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.db.models import User, ArtifactMessage
    from app.services import artifact_chat
    from app.services import artifacts as art_svc

    await client.get("/artifacts")
    async with SessionLocal() as db:
        owner = (await db.execute(
            select(User).where(User.google_sub == "test-user"))).scalars().first()
        resp = await client.post("/agents", json={"name": "Sum-Agent2"})
        agent_id = UUID(resp.json()["id"])
        art = await art_svc.create_instance(
            db, owner_id=owner.id, agent_id=agent_id, title="Sum2", output_type="html")
        for i in range(4):
            db.add(ArtifactMessage(artifact_id=art.id,
                role="user" if i % 2 == 0 else "assistant", content=f"k-{i}"))
        await db.commit()
        art_id = art.id

    called = {"v": False}
    async def fake_complete(system, message): return "ok"
    async def fake_summarize(prev, to_fold):
        called["v"] = True
        return "X"

    async with SessionLocal() as db:
        await artifact_chat.run_turn(db, artifact_id=art_id,
            complete=fake_complete, summarize=fake_summarize)
    assert called["v"] is False     # kein Overflow → kein Summarize
