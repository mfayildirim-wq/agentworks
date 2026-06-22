"""Echo-Executor: bestätigt nur den Input, ohne LLM-Call. Für Smoke-Tests."""

from __future__ import annotations

from agent_runtime.events import RunEvent, RunEventType
from agent_runtime.executor import AgentExecutor, ExecutorContext, ExecutorResult
from agent_runtime.spec import WorkSpec


class EchoExecutor(AgentExecutor):
    async def run(self, work: WorkSpec, ctx: ExecutorContext) -> ExecutorResult:
        agent = work.agents[0]
        ctx.on_event(
            RunEvent(
                type=RunEventType.RUN_STARTED,
                run_id=work.run_id,
                payload={"mode": work.mode.value, "agents": [a.name for a in work.agents]},
            )
        )
        reply = f"[echo:{agent.name}] {work.initial_message}"
        ctx.on_event(
            RunEvent(
                type=RunEventType.AGENT_MESSAGE,
                run_id=work.run_id,
                agent_id=agent.id,
                agent_name=agent.name,
                content=reply,
                tokens_in=len(work.initial_message.split()),
                tokens_out=len(reply.split()),
            )
        )
        ctx.on_event(RunEvent(type=RunEventType.RUN_COMPLETED, run_id=work.run_id))
        return ExecutorResult(
            final_message=reply,
            total_tokens_in=len(work.initial_message.split()),
            total_tokens_out=len(reply.split()),
            total_cost_usd=0.0,
        )
