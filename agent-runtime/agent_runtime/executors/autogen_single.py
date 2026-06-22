"""Single-Agent-Executor via AutoGen AssistantAgent + Anthropic."""

from __future__ import annotations

from agent_runtime.events import RunEvent, RunEventType
from agent_runtime.executor import AgentExecutor, ExecutorContext, ExecutorResult
from agent_runtime.model_client import make_model_client, provider_supports_tools
from agent_runtime.pricing import cost
from agent_runtime.spec import WorkSpec


class AutoGenSingleExecutor(AgentExecutor):
    async def run(self, work: WorkSpec, ctx: ExecutorContext) -> ExecutorResult:
        from autogen_agentchat.agents import AssistantAgent
        from autogen_agentchat.messages import TextMessage
        from autogen_core import CancellationToken

        agent_spec = work.agents[0]
        client = make_model_client(agent_spec, ctx)
        attach = ctx.tools if provider_supports_tools(agent_spec.provider) else []
        agent = AssistantAgent(
            name=_safe_name(agent_spec.name),
            model_client=client,
            system_message=agent_spec.system_prompt,
            tools=attach or None,
            reflect_on_tool_use=bool(attach),
        )

        ctx.on_event(
            RunEvent(
                type=RunEventType.RUN_STARTED,
                run_id=work.run_id,
                payload={"mode": "single", "model": agent_spec.model},
            )
        )

        result_msg = await agent.on_messages(
            [TextMessage(content=work.initial_message, source="user")],
            cancellation_token=CancellationToken(),
        )

        text = result_msg.chat_message.content if result_msg.chat_message else ""
        usage = getattr(result_msg.chat_message, "models_usage", None)
        tokens_in = getattr(usage, "prompt_tokens", 0) if usage else 0
        tokens_out = getattr(usage, "completion_tokens", 0) if usage else 0
        usd = cost(agent_spec.model, tokens_in, tokens_out)

        ctx.on_event(
            RunEvent(
                type=RunEventType.AGENT_MESSAGE,
                run_id=work.run_id,
                agent_id=agent_spec.id,
                agent_name=agent_spec.name,
                content=text,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=usd,
            )
        )
        ctx.on_event(
            RunEvent(
                type=RunEventType.TOKEN_USAGE,
                run_id=work.run_id,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=usd,
            )
        )
        ctx.on_event(RunEvent(type=RunEventType.RUN_COMPLETED, run_id=work.run_id))

        await client.close()
        return ExecutorResult(
            final_message=text,
            total_tokens_in=tokens_in,
            total_tokens_out=tokens_out,
            total_cost_usd=usd,
        )


def _safe_name(name: str) -> str:
    return "".join(c if c.isalnum() or c == "_" else "_" for c in name) or "agent"
