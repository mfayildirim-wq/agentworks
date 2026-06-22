from uuid import UUID

import pytest

from app.db.session import SessionLocal
from app.services.runs import build_work_spec


async def _make_work_with_loop(client, monkeypatch) -> tuple[str, str]:
    # Agent + Template + Instanz erzeugen (deckt den realen Pfad ab).
    # Redis-Enqueue stubben (kein Redis im Test) — via monkeypatch, damit der Patch
    # nach dem Test sauber zurückgerollt wird (kein State-Leak in Folgetests).
    import app.workers as workers

    monkeypatch.setattr(workers.execute_run, "send", lambda *a, **k: None)

    a = await client.post(
        "/agents", json={"name": "P", "role": "x", "skills": ["a"], "visibility": "public"}
    )
    aid = a.json()["id"]
    t = await client.post(
        "/templates",
        json={
            "title": "T",
            "visibility": "public",
            "output_type": "html",
            "max_iterations": 4,
            "config": {"agent_ids": [aid], "prompt_template": "Plane {{x}}."},
            "input_schema": [{"key": "x", "label": "X", "type": "string", "required": True}],
        },
    )
    tid = t.json()["id"]
    inst = await client.post(f"/templates/{tid}/instantiate", json={"inputs": {"x": "Rom"}})
    artifact_id = inst.json()["artifact_id"]

    # Instanziieren startet keinen Lauf mehr (konversationell) — den Loop-Run liefert
    # der weiterhin gültige adjust-Pfad (setzt loop_config.artifact_id).
    from sqlalchemy import select

    from app.db.models import User, WorkRun
    from app.services import artifacts as art_svc

    async with SessionLocal() as db:
        # Den authentifizierten Test-Nutzer (= Instanz-Owner) deterministisch wählen;
        # select(User).first() ist auf der geteilten Test-DB nicht zuverlässig der Auth-Nutzer.
        owner = (await db.execute(
            select(User).where(User.google_sub == "test-user")
        )).scalars().first()
        run_id = await art_svc.adjust(db, UUID(artifact_id), owner.id, "Plane Rom.")
        wr = await db.get(WorkRun, run_id)
        return str(wr.work_id), str(run_id)


@pytest.mark.asyncio
async def test_build_work_spec_populates_loop(client, monkeypatch):
    _work_id, run_id = await _make_work_with_loop(client, monkeypatch)
    async with SessionLocal() as db:
        spec = await build_work_spec(db, UUID(run_id))
    assert spec.loop is not None
    assert spec.loop.enabled is True
    # Run kommt aus dem adjust-Pfad (_ADJUST_MAX_ITERATIONS=2, _ADJUST_MAX_COST=1.0).
    assert spec.loop.max_iterations == 2
    assert spec.loop.max_cost_usd == 1.0
    assert spec.loop.output_type == "html"
