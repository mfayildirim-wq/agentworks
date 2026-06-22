from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.models import Visibility


class RatingIn(BaseModel):
    stars: int = Field(ge=1, le=5)
    comment: str = Field("", max_length=1000)


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    role: str = ""
    domain: str = ""
    system_prompt: str | None = None
    model: str = "deepseek-chat"
    provider: str = "deepseek"
    api_key: str | None = None
    temperature: float = 0.7
    tools: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    visibility: Visibility = Visibility.PRIVATE
    price_per_run: float = 0.0
    avatar_url: str | None = None


class AgentUpdate(BaseModel):
    description: str | None = None
    role: str | None = None
    domain: str | None = None
    system_prompt: str | None = None
    model: str | None = None
    provider: str | None = None
    api_key: str | None = None
    temperature: float | None = None
    tools: list[str] | None = None
    skills: list[str] | None = None
    visibility: Visibility | None = None
    price_per_run: float | None = None
    avatar_url: str | None = None


class AgentOut(BaseModel):
    id: UUID
    owner_id: UUID
    name: str
    description: str
    role: str
    domain: str
    avatar_url: str | None
    visibility: Visibility
    price_per_run: float
    model: str
    provider: str = "anthropic"
    has_api_key: bool = False
    temperature: float
    system_prompt: str
    skills: list[str]
    tools: list[str]
    rating_avg: float = 0.0
    rating_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProfileExtract(BaseModel):
    name: str = ""
    role: str = ""
    domain: str = ""
    seniority: str = ""
    skills: list[str] = Field(default_factory=list)
    summary: str = ""


class AgentWorkRef(BaseModel):
    id: UUID
    title: str
    image_url: str | None = None


class ReviewOut(BaseModel):
    stars: int
    comment: str
    user_name: str
    created_at: datetime
