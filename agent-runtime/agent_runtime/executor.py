from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any

from agent_runtime.events import RunEvent
from agent_runtime.spec import WorkSpec

EventSink = Callable[[RunEvent], None]


@dataclass
class ExecutorContext:
    """Konfiguration + Callbacks für eine Ausführung."""

    api_key: str
    on_event: EventSink
    ollama_url: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    tools: list[Any] = field(default_factory=list)


@dataclass
class ExecutorResult:
    final_message: str
    total_tokens_in: int
    total_tokens_out: int
    total_cost_usd: float
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentExecutor(ABC):
    """Plattform-eigene Abstraktion. Konkrete Implementierungen kapseln AutoGen,
    LangGraph, Claude Agent SDK etc."""

    @abstractmethod
    async def run(self, work: WorkSpec, ctx: ExecutorContext) -> ExecutorResult:
        """Vollständige synchrone Ausführung, ruft `ctx.on_event` pro Event."""

    async def stream(self, work: WorkSpec, ctx: ExecutorContext) -> AsyncIterator[RunEvent]:
        """Optional: Events als async iterator (default: per Sammler über run())."""
        collected: list[RunEvent] = []

        def collect(event: RunEvent) -> None:
            collected.append(event)

        wrapped = ExecutorContext(
            api_key=ctx.api_key,
            on_event=collect,
            ollama_url=ctx.ollama_url,
            extra=ctx.extra,
            tools=ctx.tools,
        )
        await self.run(work, wrapped)
        for event in collected:
            yield event
