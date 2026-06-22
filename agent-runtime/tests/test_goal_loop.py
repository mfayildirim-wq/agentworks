from uuid import uuid4

import pytest

from agent_runtime.events import RunEventType
from agent_runtime.executor import ExecutorResult
from agent_runtime.executors.goal_loop import (
    build_loop_protocol,
    drive_loop,
    extract_fenced,
    feedback_message,
    is_done,
)
from agent_runtime.spec import AgentSpec, LoopConfig, RunMode, WorkSpec


def test_workspec_accepts_loop_config():
    work = WorkSpec(
        id=uuid4(),
        run_id=uuid4(),
        title="t",
        goal="g",
        mode=RunMode.SINGLE,
        agents=[AgentSpec(id=uuid4(), name="A", system_prompt="x")],
        initial_message="hi",
        loop=LoopConfig(enabled=True, max_iterations=3, output_type="html"),
    )
    assert work.loop is not None
    assert work.loop.enabled is True
    assert work.loop.max_iterations == 3
    assert work.loop.output_type == "html"


def test_workspec_loop_defaults_none():
    work = WorkSpec(
        id=uuid4(),
        run_id=uuid4(),
        title="t",
        goal="g",
        agents=[AgentSpec(id=uuid4(), name="A", system_prompt="x")],
        initial_message="hi",
    )
    assert work.loop is None


def test_extract_fenced_prefers_matching_language():
    text = "Vorrede\n```text\nignoriere\n```\nDanach\n```html\n<h1>Hi</h1>\n```\nEnde"
    assert extract_fenced(text, "html") == "<h1>Hi</h1>"


def test_extract_fenced_falls_back_to_last_block():
    text = "```\n<p>nur ein Block</p>\n```"
    assert extract_fenced(text, "html") == "<p>nur ein Block</p>"


def test_extract_fenced_returns_none_without_block():
    assert extract_fenced("kein code hier", "html") is None


def test_is_done_detects_marker_case_insensitive():
    assert is_done("...\nstatus: done") is True
    assert is_done("STATUS: DONE — fertig") is True
    assert is_done("STATUS: CONTINUE — offen: x") is False
    assert is_done("kein marker") is False


def test_build_loop_protocol_mentions_output_and_status():
    p = build_loop_protocol("html", "Reiseplan Rom", ["Hotels", "Tagesplan"])
    assert "html" in p.lower()
    assert "STATUS: DONE" in p
    assert "STATUS: CONTINUE" in p
    assert "Hotels" in p and "Tagesplan" in p


def test_feedback_message_asks_for_full_artifact():
    m = feedback_message("html")
    assert "html" in m.lower()
    assert "komplett" in m.lower()


def _work(loop):
    return WorkSpec(
        id=uuid4(),
        run_id=uuid4(),
        title="t",
        goal="Reiseplan",
        mode=RunMode.SINGLE,
        agents=[AgentSpec(id=uuid4(), name="A", system_prompt="x", provider="ollama")],
        initial_message="los",
        loop=loop,
    )


@pytest.mark.asyncio
async def test_drive_loop_stops_on_done():
    outs = iter(
        [
            "Entwurf\n```html\n<h1>v1</h1>\n```\nSTATUS: CONTINUE — offen: mehr",
            "Final\n```html\n<h1>v2</h1>\n```\nSTATUS: DONE",
        ]
    )

    async def turn(msg):
        return (next(outs), 10, 20)

    events = []
    loop = LoopConfig(enabled=True, max_iterations=5, output_type="html")
    work = _work(loop)
    res = await drive_loop(
        turn, work=work, loop=loop, agent_spec=work.agents[0], on_event=events.append
    )

    assert isinstance(res, ExecutorResult)
    assert res.metadata["stop_reason"] == "done"
    assert res.metadata["iterations"] == 2
    assert res.metadata["artifact"] == "<h1>v2</h1>"
    assert res.metadata["output_type"] == "html"
    types = [e.type for e in events]
    assert RunEventType.RUN_STARTED in types
    assert types.count(RunEventType.AGENT_MESSAGE) == 2
    assert RunEventType.ARTIFACT_UPDATED in types
    assert RunEventType.RUN_COMPLETED in types


@pytest.mark.asyncio
async def test_drive_loop_stops_on_max_iterations():
    async def turn(msg):
        return ("```html\n<p>x</p>\n```\nSTATUS: CONTINUE — offen: alles", 5, 5)

    loop = LoopConfig(enabled=True, max_iterations=3, output_type="html")
    work = _work(loop)
    res = await drive_loop(
        turn, work=work, loop=loop, agent_spec=work.agents[0], on_event=lambda e: None
    )
    assert res.metadata["stop_reason"] == "limit"
    assert res.metadata["iterations"] == 3


@pytest.mark.asyncio
async def test_drive_loop_feeds_back_between_iterations():
    seen = []

    async def turn(msg):
        seen.append(msg)
        # erste Iteration: weiter; zweite: fertig
        status = "DONE" if len(seen) >= 2 else "CONTINUE — offen: x"
        return (f"```html\n<p>{len(seen)}</p>\n```\nSTATUS: {status}", 1, 1)

    loop = LoopConfig(enabled=True, max_iterations=5, output_type="html")
    work = _work(loop)
    await drive_loop(turn, work=work, loop=loop, agent_spec=work.agents[0], on_event=lambda e: None)
    assert seen[0] == "los"  # initial_message
    assert "komplett" in seen[1].lower()  # feedback


@pytest.mark.asyncio
async def test_drive_loop_ollama_provider_is_zero_cost():
    async def turn(msg):
        return ("```html\n<p>x</p>\n```\nSTATUS: DONE", 1000, 2000)

    loop = LoopConfig(enabled=True, max_iterations=2, output_type="html")
    work = _work(loop)  # provider="ollama"
    res = await drive_loop(
        turn, work=work, loop=loop, agent_spec=work.agents[0], on_event=lambda e: None
    )
    assert res.total_cost_usd == 0.0


def test_extract_fenced_tolerates_trailing_space_in_lang_tag():
    text = "```html   \n<h1>Hi</h1>\n```"
    assert extract_fenced(text, "html") == "<h1>Hi</h1>"


@pytest.mark.asyncio
async def test_drive_loop_stops_on_cost():
    # Nicht-Ollama-Provider → echte Preisberechnung; kleines max_cost erzwingt cost-Stop.
    async def turn(msg):
        return ("```html\n<p>x</p>\n```\nSTATUS: CONTINUE — offen: alles", 1000, 1000)

    work = WorkSpec(
        id=uuid4(),
        run_id=uuid4(),
        title="t",
        goal="g",
        mode=RunMode.SINGLE,
        agents=[
            AgentSpec(
                id=uuid4(),
                name="A",
                system_prompt="x",
                provider="anthropic",
                model="claude-sonnet-4-6",
            )
        ],
        initial_message="los",
        loop=LoopConfig(enabled=True, max_iterations=10, max_cost_usd=0.01, output_type="html"),
    )
    res = await drive_loop(
        turn, work=work, loop=work.loop, agent_spec=work.agents[0], on_event=lambda e: None
    )
    assert res.metadata["stop_reason"] == "cost"
    assert res.metadata["iterations"] == 1
    assert res.total_cost_usd >= 0.01


@pytest.mark.asyncio
async def test_goal_loop_executor_delegates_to_drive_loop(monkeypatch):
    from agent_runtime.executor import ExecutorContext
    from agent_runtime.executors import goal_loop as gl

    closed = {"called": False}

    async def fake_turn_builder(agent_spec, ctx):
        async def turn(msg):
            return ("```html\n<h1>done</h1>\n```\nSTATUS: DONE", 1, 1)

        async def closer():
            closed["called"] = True

        return turn, closer

    monkeypatch.setattr(gl, "_build_turn_fn", fake_turn_builder)

    loop = LoopConfig(enabled=True, max_iterations=3, output_type="html")
    work = _work(loop)
    ctx = ExecutorContext(api_key="x", on_event=lambda e: None)
    res = await gl.GoalLoopExecutor().run(work, ctx)
    assert res.metadata["stop_reason"] == "done"
    assert res.metadata["artifact"] == "<h1>done</h1>"
    assert closed["called"] is True  # closer wird im finally aufgerufen (kein Client-Leak)
