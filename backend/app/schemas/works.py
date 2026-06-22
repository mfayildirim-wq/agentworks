from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.models import RunMode, RunStatus, Visibility


class WorkAgentIn(BaseModel):
    agent_id: UUID
    role_in_work: str = ""
    handoff_targets: list[UUID] = Field(default_factory=list)


class WorkCreate(BaseModel):
    title: str
    goal: str
    expected_outcome: str = ""
    initial_message: str
    mode: RunMode = RunMode.SINGLE
    visibility: Visibility = Visibility.PRIVATE
    max_turns: int = 12
    max_tokens: int = 50_000
    agents: list[WorkAgentIn]


class WorkAgentOut(BaseModel):
    agent_id: UUID
    role_in_work: str
    handoff_targets: list[UUID]
    name: str
    model: str

    model_config = {"from_attributes": True}


class WorkOut(BaseModel):
    id: UUID
    owner_id: UUID
    title: str
    goal: str
    expected_outcome: str
    initial_message: str
    mode: RunMode
    visibility: Visibility
    max_turns: int
    max_tokens: int
    agents: list[WorkAgentOut]
    estimated_cost_usd: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RunOut(BaseModel):
    id: UUID
    work_id: UUID
    status: RunStatus
    started_at: datetime
    finished_at: datetime | None
    total_tokens_in: int
    total_tokens_out: int
    total_cost: float
    result: dict | None
    error: str | None

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    id: UUID
    run_id: UUID
    agent_id: UUID | None
    agent_name: str
    role: str
    content: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    ts: datetime

    model_config = {"from_attributes": True}
