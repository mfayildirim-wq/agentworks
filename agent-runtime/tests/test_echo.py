import pytest
from uuid import uuid4

from agent_runtime.events import RunEvent, RunEventType
from agent_runtime.executor import ExecutorContext
from agent_runtime.executors.echo import EchoExecutor
from agent_runtime.spec import AgentSpec, RunMode, WorkSpec


@pytest.mark.asyncio
async def test_echo_executor_emits_started_message_completed():
    received: list[RunEvent] = []

    work = WorkSpec(
        id=uuid4(),
        run_id=uuid4(),
        title="t",
        goal="g",
        mode=RunMode.SINGLE,
        agents=[AgentSpec(id=uuid4(), name="A", system_prompt="x")],
        initial_message="hello world",
    )
    ctx = ExecutorContext(api_key="x", on_event=received.append)

    result = await EchoExecutor().run(work, ctx)

    assert result.final_message.startswith("[echo:A]")
    types = [e.type for e in received]
    assert RunEventType.RUN_STARTED in types
    assert RunEventType.AGENT_MESSAGE in types
    assert RunEventType.RUN_COMPLETED in types
