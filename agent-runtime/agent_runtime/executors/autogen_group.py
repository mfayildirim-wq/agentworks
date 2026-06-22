"""Selector-Group-Chat-Executor via AutoGen."""

from __future__ import annotations

from agent_runtime.events import RunEvent, RunEventType
from agent_runtime.executor import AgentExecutor, ExecutorContext, ExecutorResult
from agent_runtime.model_client import make_model_client
from agent_runtime.pricing import cost
from agent_runtime.spec import AgentSpec, WorkSpec


class AutoGenGroupExecutor(AgentExecutor):
    async def run(self, work: WorkSpec, ctx: ExecutorContext) -> ExecutorResult:
        from autogen_agentchat.agents import AssistantAgent
        from autogen_agentchat.conditions import MaxMessageTermination
        from autogen_agentchat.teams import SelectorGroupChat

        clients = [make_model_client(a, ctx) for a in work.agents]
        autogen_agents = [_make_agent(a, c) for a, c in zip(work.agents, clients)]
        team = SelectorGroupChat(
            participants=autogen_agents,
            model_client=clients[0],
            termination_condition=MaxMessageTermination(max_messages=work.max_turns),
        )

        ctx.on_event(
            RunEvent(
                type=RunEventType.RUN_STARTED,
                run_id=work.run_id,
                payload={"mode": "group", "agents": [a.name for a in work.agents]},
            )
        )

        total_in = total_out = 0
        last_text = ""

        async for msg in team.run_stream(task=work.initial_message):
            source = getattr(msg, "source", None)
            content = getattr(msg, "content", None)
            if not source or content is None:
                continue
            agent_spec = _find_agent(work.agents, source)
            usage = getattr(msg, "models_usage", None)
            tin = getattr(usage, "prompt_tokens", 0) if usage else 0
            tout = getattr(usage, "completion_tokens", 0) if usage else 0
            usd = cost(agent_spec.model if agent_spec else work.agents[0].model, tin, tout)
            total_in += tin
            total_out += tout
            last_text = content if isinstance(content, str) else last_text
            ctx.on_event(
                RunEvent(
                    type=RunEventType.AGENT_MESSAGE,
                    run_id=work.run_id,
                    agent_id=agent_spec.id if agent_spec else None,
                    agent_name=source,
                    content=last_text,
                    tokens_in=tin,
                    tokens_out=tout,
                    cost_usd=usd,
                )
            )

        total_cost = cost(work.agents[0].model, total_in, total_out)
        ctx.on_event(
            RunEvent(
                type=RunEventType.TOKEN_USAGE,
                run_id=work.run_id,
                tokens_in=total_in,
                tokens_out=total_out,
                cost_usd=total_cost,
            )
        )
        ctx.on_event(RunEvent(type=RunEventType.RUN_COMPLETED, run_id=work.run_id))
        for c in clients:
            await c.close()
        return ExecutorResult(
            final_message=last_text,
            total_tokens_in=total_in,
            total_tokens_out=total_out,
            total_cost_usd=total_cost,
        )


def _make_agent(spec: AgentSpec, client):
    from autogen_agentchat.agents import AssistantAgent

    return AssistantAgent(
        name=_safe_name(spec.name),
        model_client=client,
        system_message=spec.system_prompt,
        description=spec.description or spec.role or spec.name,
    )


def _find_agent(agents: list[AgentSpec], source: str) -> AgentSpec | None:
    target = _safe_name(source)
    for a in agents:
        if _safe_name(a.name) == target:
            return a
    return None


def _safe_name(name: str) -> str:
    return "".join(c if c.isalnum() or c == "_" else "_" for c in name) or "agent"
