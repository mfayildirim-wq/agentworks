from __future__ import annotations

from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class RunMode(str, Enum):
    SINGLE = "single"
    GROUP = "group"
    SWARM = "swarm"
    GRAPH = "graph"


class AgentSpec(BaseModel):
    """Runtime-Sicht auf einen Agenten (aus agent_versions geladen)."""

    id: UUID
    name: str
    description: str = ""
    role: str = ""
    system_prompt: str
    model: str = "claude-sonnet-4-6"
    provider: str = "anthropic"
    api_key: str | None = None
    temperature: float = 0.7
    tools: list[str] = Field(default_factory=list)
    handoff_targets: list[UUID] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LoopConfig(BaseModel):
    """Ziel-Loop-Konfiguration (aus dem Template übernommen)."""

    enabled: bool = False
    max_iterations: int = 8
    max_cost_usd: float = 1.0
    output_type: str = "html"
    success_criteria: list[str] | None = None


class WorkSpec(BaseModel):
    """Runtime-Sicht auf einen Work."""

    id: UUID
    run_id: UUID
    title: str
    goal: str
    expected_outcome: str = ""
    mode: RunMode = RunMode.SINGLE
    agents: list[AgentSpec]
    initial_message: str
    max_turns: int = 12
    max_tokens: int = 50_000
    metadata: dict[str, Any] = Field(default_factory=dict)
    loop: LoopConfig | None = None
