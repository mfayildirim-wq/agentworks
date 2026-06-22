"""GraphFlow-Executor: führt Agenten entlang eines DAG aus.

Phase-3-Variante. AutoGen GraphFlow erwartet eine DiGraph; wir bekommen
Knoten/Kanten als IDs.
"""

from __future__ import annotations

from agent_runtime.events import RunEvent, RunEventType
from agent_runtime.executor import AgentExecutor, ExecutorContext, ExecutorResult
from agent_runtime.model_client import make_model_client
from agent_runtime.pricing import cost
from agent_runtime.spec import WorkSpec


class AutoGenGraphFlowExecutor(AgentExecutor):
    async def run(self, work: WorkSpec, ctx: ExecutorContext) -> ExecutorResult:
        try:
            from autogen_agentchat.teams import DiGraphBuilder, GraphFlow
        except ImportError as exc:  # AutoGen-Version ohne GraphFlow
            ctx.on_event(
                RunEvent(
                    type=RunEventType.ERROR,
                    run_id=work.run_id,
                    content=f"GraphFlow nicht verfügbar: {exc}",
                )
            )
            raise

        from autogen_agentchat.agents import AssistantAgent

        clients = []
        autogen_by_id = {}
        builder = DiGraphBuilder()
        for spec in work.agents:
            cl = make_model_client(spec, ctx)
            clients.append(cl)
            agent = AssistantAgent(
                name=_safe_name(spec.name),
                model_client=cl,
                system_message=spec.system_prompt,
            )
            autogen_by_id[spec.id] = agent
            builder.add_node(agent)

        for spec in work.agents:
            for target_id in spec.handoff_targets:
                if target_id in autogen_by_id:
                    builder.add_edge(autogen_by_id[spec.id], autogen_by_id[target_id])

        team = GraphFlow(
            participants=list(autogen_by_id.values()),
            graph=builder.build(),
        )

        ctx.on_event(
            RunEvent(
                type=RunEventType.RUN_STARTED,
                run_id=work.run_id,
                payload={"mode": "graph", "agents": [a.name for a in work.agents]},
            )
        )

        total_in = total_out = 0
        last_text = ""
        async for msg in team.run_stream(task=work.initial_message):
            source = getattr(msg, "source", None)
            content = getattr(msg, "content", None)
            if not source or content is None:
                continue
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
                    agent_name=source,
                    content=last_text,
                    tokens_in=tin,
                    tokens_out=tout,
                )
            )

        total_cost = cost(work.agents[0].model, total_in, total_out)
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
