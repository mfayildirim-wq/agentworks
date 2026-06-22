from __future__ import annotations

from agent_runtime.executor import AgentExecutor
from agent_runtime.spec import RunMode


def create_executor(mode: RunMode) -> AgentExecutor:
    if mode == RunMode.SINGLE:
        from agent_runtime.executors.autogen_single import AutoGenSingleExecutor

        return AutoGenSingleExecutor()
    if mode == RunMode.GROUP:
        from agent_runtime.executors.autogen_group import AutoGenGroupExecutor

        return AutoGenGroupExecutor()
    if mode == RunMode.SWARM:
        from agent_runtime.executors.autogen_swarm import AutoGenSwarmExecutor

        return AutoGenSwarmExecutor()
    if mode == RunMode.GRAPH:
        from agent_runtime.executors.autogen_graph import AutoGenGraphFlowExecutor

        return AutoGenGraphFlowExecutor()
    raise ValueError(f"Unknown run mode: {mode}")
