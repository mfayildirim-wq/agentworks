"""Ziel-Loop-Executor (textkonvention-basiert, modell-agnostisch).

Mechanik: kein Tool-Calling (Ollama-Default kann es nicht). Der Loop ergänzt den
System-Prompt um ein Protokoll; der Agent gibt pro Iteration das komplette Artefakt in
einem Fenced-Block + eine STATUS-Zeile aus. Siehe Spec Abschnitt 5.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from uuid import UUID

from agent_runtime.events import RunEvent, RunEventType
from agent_runtime.executor import AgentExecutor, ExecutorContext, ExecutorResult
from agent_runtime.model_client import make_model_client, provider_supports_tools
from agent_runtime.pricing import cost as price_cost
from agent_runtime.spec import AgentSpec, LoopConfig, WorkSpec

TurnFn = Callable[[str], Awaitable[tuple[str, int, int]]]

# Trailing-Whitespace im Sprach-Tag tolerieren (manche Modelle hängen Spaces an).
# Bekannte Grenze: non-greedy `.*?` schneidet bei verschachtelten ```-Fences am inneren
# Fence ab — für HTML-Artefakte praktisch selten, bewusst akzeptiert.
_FENCE_RE = re.compile(r"```([A-Za-z0-9_+-]*)[ \t]*\n(.*?)```", re.DOTALL)
_DONE_RE = re.compile(r"STATUS:\s*DONE", re.IGNORECASE)


def extract_fenced(text: str, output_type: str) -> str | None:
    """Letzten Fenced-Block extrahieren; bevorzugt den, dessen Sprache == output_type."""
    blocks = _FENCE_RE.findall(text or "")
    if not blocks:
        return None
    matching = [body for lang, body in blocks if lang.lower() == output_type.lower()]
    chosen = matching[-1] if matching else blocks[-1][1]
    return chosen.strip()


def is_done(text: str) -> bool:
    """True bei `STATUS: DONE` (case-insensitive).

    Bewusster Tradeoff der Textkonvention (Ollama kann kein Tool-Calling): es wird der
    gesamte Text gescannt, nicht nur die Zeile nach dem letzten Fence. Theoretisch kann
    ein Modell `STATUS: DONE` im Fließtext/Kommentar erwähnen und damit früh stoppen —
    das harte Iterations-/Kosten-Limit bleibt als Sicherheitsnetz.
    """
    return bool(_DONE_RE.search(text or ""))


def build_loop_protocol(output_type: str, goal: str, success_criteria: list[str] | None) -> str:
    crit = ""
    if success_criteria:
        items = "\n".join(f"- {c}" for c in success_criteria)
        crit = f"\nErfolgskriterien (alle müssen erfüllt sein):\n{items}\n"
    return (
        "\n\n## Arbeitsprotokoll (WICHTIG)\n"
        f"Ziel: {goal}\n{crit}"
        f"Arbeite iterativ auf das Ziel hin. Gib in JEDER Antwort das KOMPLETTE Ergebnis "
        f"als zusammenhängenden ```{output_type}-Codeblock aus (keine Auslassungen, kein "
        "„unverändert“). Schreibe danach GENAU EINE Statuszeile:\n"
        "- `STATUS: DONE` wenn das Ziel vollständig erfüllt ist, ODER\n"
        "- `STATUS: CONTINUE — offen: <was noch fehlt>` wenn noch etwas fehlt.\n"
    )


def feedback_message(output_type: str) -> str:
    return (
        "Verbessere/ergänze das Ergebnis auf Basis der offenen Punkte. Gib die KOMPLETTE "
        f"aktualisierte Fassung erneut als ```{output_type}-Codeblock aus und schließe mit "
        "einer STATUS-Zeile ab."
    )


def _iteration_cost(agent_spec: AgentSpec, tokens_in: int, tokens_out: int) -> float:
    if (agent_spec.provider or "").lower() == "ollama":
        return 0.0
    return price_cost(agent_spec.model, tokens_in, tokens_out)


async def drive_loop(
    turn_fn: TurnFn,
    *,
    work: WorkSpec,
    loop: LoopConfig,
    agent_spec: AgentSpec,
    on_event: Callable[[RunEvent], None],
) -> ExecutorResult:
    """Reine Schleife (ohne AutoGen). `turn_fn(message)` -> (text, tokens_in, tokens_out)."""
    run_id: UUID = work.run_id
    on_event(
        RunEvent(
            type=RunEventType.RUN_STARTED,
            run_id=run_id,
            payload={"mode": "goal_loop", "model": agent_spec.model},
        )
    )

    artifact = ""
    last_text = ""
    total_in = total_out = 0
    total_cost = 0.0
    stop_reason = "limit"
    message = work.initial_message
    iteration = 0

    while iteration < loop.max_iterations:
        iteration += 1
        text, t_in, t_out = await turn_fn(message)
        last_text = text
        total_in += t_in
        total_out += t_out
        usd = _iteration_cost(agent_spec, t_in, t_out)
        total_cost += usd

        extracted = extract_fenced(text, loop.output_type)
        if extracted:
            artifact = extracted

        on_event(
            RunEvent(
                type=RunEventType.AGENT_MESSAGE,
                run_id=run_id,
                agent_id=agent_spec.id,
                agent_name=agent_spec.name,
                content=text,
                tokens_in=t_in,
                tokens_out=t_out,
                cost_usd=usd,
            )
        )
        on_event(
            RunEvent(
                type=RunEventType.ARTIFACT_UPDATED,
                run_id=run_id,
                payload={
                    "iteration": iteration,
                    "content": artifact,
                    "output_type": loop.output_type,
                    # False, wenn diese Iteration keinen neuen Fenced-Block lieferte
                    # (content ist dann der vorherige Stand) — hilft 5c-Streaming.
                    "updated": bool(extracted),
                },
            )
        )
        on_event(
            RunEvent(
                type=RunEventType.TOKEN_USAGE,
                run_id=run_id,
                tokens_in=t_in,
                tokens_out=t_out,
                cost_usd=usd,
            )
        )

        if is_done(text):
            stop_reason = "done"
            break
        if loop.max_cost_usd > 0 and total_cost >= loop.max_cost_usd:
            stop_reason = "cost"
            break
        message = feedback_message(loop.output_type)

    on_event(RunEvent(type=RunEventType.RUN_COMPLETED, run_id=run_id))
    return ExecutorResult(
        final_message=artifact or last_text,
        total_tokens_in=total_in,
        total_tokens_out=total_out,
        total_cost_usd=total_cost,
        metadata={
            "artifact": artifact,
            "output_type": loop.output_type,
            "iterations": iteration,
            "stop_reason": stop_reason,
        },
    )


def _safe_name(name: str) -> str:
    return "".join(c if c.isalnum() or c == "_" else "_" for c in name) or "agent"


async def _build_turn_fn(
    agent_spec: AgentSpec, ctx: ExecutorContext
) -> tuple[TurnFn, Callable[[], Awaitable[None]]]:
    """Baut ein turn_fn aus einem persistenten AssistantAgent + einen Closer."""
    from autogen_agentchat.agents import AssistantAgent
    from autogen_agentchat.messages import TextMessage
    from autogen_core import CancellationToken

    client = make_model_client(agent_spec, ctx)
    try:
        # EIN persistenter Agent über alle Iterationen → Konversationskontext wächst
        # (UnboundedChatCompletionContext). Bewusst gewählt für iterative Verbesserung;
        # das harte max_iterations/max_cost-Limit begrenzt das Wachstum. Bei sehr kleinen
        # Modell-Kontextfenstern wäre ein BufferedChatCompletionContext die Ausbaustufe.
        attach = ctx.tools if provider_supports_tools(agent_spec.provider) else []
        agent = AssistantAgent(
            name=_safe_name(agent_spec.name),
            model_client=client,
            system_message=agent_spec.system_prompt,
            tools=attach or None,
            reflect_on_tool_use=bool(attach),
        )
    except BaseException:
        # Client schließen, falls die Agent-Konstruktion scheitert (sonst Leak, da der
        # Aufrufer den closer noch nicht erhalten hat).
        await client.close()
        raise

    async def turn(message: str) -> tuple[str, int, int]:
        res = await agent.on_messages(
            [TextMessage(content=message, source="user")],
            cancellation_token=CancellationToken(),
        )
        text = res.chat_message.content if res.chat_message else ""
        usage = getattr(res.chat_message, "models_usage", None)
        t_in = getattr(usage, "prompt_tokens", 0) if usage else 0
        t_out = getattr(usage, "completion_tokens", 0) if usage else 0
        return text, t_in, t_out

    async def closer() -> None:
        await client.close()

    return turn, closer


class GoalLoopExecutor(AgentExecutor):
    async def run(self, work: WorkSpec, ctx: ExecutorContext) -> ExecutorResult:
        agent_spec = work.agents[0]
        loop = work.loop or LoopConfig(enabled=True)
        # Protokoll an den System-Prompt hängen (Agent persistiert über Iterationen):
        agent_spec = agent_spec.model_copy(
            update={
                "system_prompt": agent_spec.system_prompt
                + build_loop_protocol(loop.output_type, work.goal, loop.success_criteria)
            }
        )
        turn, closer = await _build_turn_fn(agent_spec, ctx)
        try:
            return await drive_loop(
                turn, work=work, loop=loop, agent_spec=agent_spec, on_event=ctx.on_event
            )
        finally:
            await closer()
