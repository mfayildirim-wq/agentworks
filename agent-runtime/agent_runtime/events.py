from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class RunEventType(str, Enum):
    RUN_STARTED = "run_started"
    AGENT_MESSAGE = "agent_message"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    HANDOFF = "handoff"
    TOKEN_USAGE = "token_usage"
    ARTIFACT_UPDATED = "artifact_updated"
    ERROR = "error"
    RUN_COMPLETED = "run_completed"


class RunEvent(BaseModel):
    type: RunEventType
    run_id: UUID
    agent_id: UUID | None = None
    agent_name: str | None = None
    content: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    payload: dict[str, Any] = Field(default_factory=dict)
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
