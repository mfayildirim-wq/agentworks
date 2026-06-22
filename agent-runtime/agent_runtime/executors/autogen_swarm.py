"""Swarm-Executor via AutoGen (Handoffs zwischen Agenten)."""

from __future__ import annotations

from agent_runtime.events import RunEvent, RunEventType
from agent_runtime.executor import AgentExecutor, ExecutorContext, ExecutorResult
from agent_runtime.model_client import make_model_client
from agent_runtime.pricing import cost
from agent_runtime.spec import AgentSpec, WorkSpec


class AutoGenSwarmExecutor(AgentExecutor):
    async def run(self, work: WorkSpec, ctx: ExecutorContext) -> ExecutorResult:
        from autogen_agentchat.agents import AssistantAgent
        from autogen_agentchat.conditions import (
            HandoffTermination,
            MaxMessageTermination,
        )
        from autogen_agentchat.teams import Swarm

        clients = [make_model_client(spec, ctx) for spec in work.agents]

        name_by_id = {a.id: _safe_name(a.name) for a in work.agents}

        def handoffs_for(spec: AgentSpec) -> list[str]:
            return [name_by_id[t] for t in spec.handoff_targets if t in name_by_id]

        autogen_agents = [
            AssistantAgent(
                name=_safe_name(spec.name),
                model_client=cl,
                system_message=spec.system_prompt,
                description=spec.description or spec.role or spec.name,
                handoffs=handoffs_for(spec),
            )
            for spec, cl in zip(work.agents, clients)
        ]

        team = Swarm(
            participants=autogen_agents,
            termination_condition=HandoffTermination(target="user")
            | MaxMessageTermination(max_messages=work.max_turns),
        )

        ctx.on_event(
            RunEvent(
                type=RunEventType.RUN_STARTED,
                run_id=work.run_id,
                payload={"mode": "swarm", "agents": [a.name for a in work.agents]},
            )
        )

        total_in = total_out = 0
        last_text = ""
        async for msg in team.run_stream(task=work.initial_message):
            source = getattr(msg, "source", None)
            content = getattr(msg, "content", None)
            if not source or content is None:
                continue
            agent_spec = next(
                (a for a in work.agents if _safe_name(a.name) == _safe_name(source)), None
            )
            usage = getattr(msg, "models_usage", None)
            tin = getattr(usage, "prompt_tokens", 0) if usage else 0
            tout = getattr(usage, "completion_tokens", 0) if usage else 0
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
                    cost_usd=cost(
                        agent_spec.model if agent_spec else work.agents[0].model, tin, tout
                    ),
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


def _safe_name(name: str) -> str:
    return "".join(c if c.isalnum() or c == "_" else "_" for c in name) or "agent"
