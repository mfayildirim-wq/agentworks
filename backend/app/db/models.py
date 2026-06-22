"""SQLAlchemy ORM models. Schema-Vorbild: docs/DATABASE_SCHEMA.md."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _now() -> datetime:
    return datetime.now(UTC)


def _pg_enum(py_enum: type[enum.Enum], name: str, **kw: Any) -> Enum:
    """Postgres-Enum, das die *Werte* (lowercase) statt der Member-Namen schreibt.

    Ohne ``values_callable`` würde SQLAlchemy ``Visibility.PUBLIC`` als ``"PUBLIC"``
    serialisieren; die DB-Enum kennt aber nur ``public`` → InvalidTextRepresentation.
    """
    return Enum(py_enum, name=name, values_callable=lambda e: [m.value for m in e], **kw)


class Visibility(str, enum.Enum):
    PRIVATE = "private"
    DRAFT = "draft"       # Entwurf — wie privat, nur für den Eigentümer sichtbar
    UNLISTED = "unlisted"
    FRIENDS = "friends"
    PUBLIC = "public"


class RunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RunMode(str, enum.Enum):
    SINGLE = "single"
    GROUP = "group"
    SWARM = "swarm"
    GRAPH = "graph"


class TemplateOutput(str, enum.Enum):
    HTML = "html"
    MARKDOWN = "markdown"
    JSON = "json"


class ScheduleCadence(str, enum.Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


class ScheduleStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class ScheduleCompletion(str, enum.Enum):
    ONCE = "once"
    UNTIL = "until"
    RECURRING = "recurring"


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = _uuid_pk()
    google_sub: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    role: Mapped[str] = mapped_column(String(16), default="", server_default="")
    topup_mode: Mapped[str] = mapped_column(String(8), default="free", server_default="free")
    # Systemadmin = erster installierender Nutzer; höchste Rolle (vormals „GOA").
    is_system_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # UI-Sprache des Nutzers: "de" | "en".
    language: Mapped[str] = mapped_column(String(2), default="de", server_default="de")
    # Eigene AI-API-Keys des Nutzers (verschlüsselt), für seine Agenten.
    openai_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    anthropic_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    # System-Keys (verschlüsselt) liegen auf dem GOA-Nutzer; deepseek ergänzt.
    deepseek_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Benachrichtigungs-Kanäle (Phase: Nachrichtendienste).
    telegram_chat_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    telegram_link_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notify_email: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_telegram: Mapped[bool] = mapped_column(Boolean, default=True)
    balance_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Friendship(Base):
    __tablename__ = "friendships"
    id: Mapped[uuid.UUID] = _uuid_pk()
    requester_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    addressee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | accepted
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    __table_args__ = (UniqueConstraint("requester_id", "addressee_id", name="uq_friendship_pair"),)


class Agent(Base):
    __tablename__ = "agents"
    id: Mapped[uuid.UUID] = _uuid_pk()
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    role: Mapped[str] = mapped_column(String(120), default="")
    domain: Mapped[str] = mapped_column(String(120), default="", index=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    visibility: Mapped[Visibility] = mapped_column(
        _pg_enum(Visibility, "visibility"), default=Visibility.PRIVATE, index=True
    )
    price_per_run: Mapped[float] = mapped_column(Float, default=0.0)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    versions: Mapped[list[AgentVersion]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
        foreign_keys="AgentVersion.agent_id",
    )
    skills: Mapped[list[AgentSkill]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )


class AgentVersion(Base):
    __tablename__ = "agent_versions"
    id: Mapped[uuid.UUID] = _uuid_pk()
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    model: Mapped[str] = mapped_column(String(80), default="claude-sonnet-4-6")
    provider: Mapped[str] = mapped_column(String(20), default="anthropic")
    temperature: Mapped[float] = mapped_column(Float, default=0.7)
    tools: Mapped[list[str]] = mapped_column(JSONB, default=list)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    agent: Mapped[Agent] = relationship(back_populates="versions", foreign_keys=[agent_id])


class AgentSkill(Base):
    __tablename__ = "agent_skills"
    __table_args__ = (UniqueConstraint("agent_id", "skill"),)
    id: Mapped[uuid.UUID] = _uuid_pk()
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), index=True
    )
    skill: Mapped[str] = mapped_column(String(80), index=True)

    agent: Mapped[Agent] = relationship(back_populates="skills")


class Work(Base):
    __tablename__ = "works"
    id: Mapped[uuid.UUID] = _uuid_pk()
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    goal: Mapped[str] = mapped_column(Text)
    expected_outcome: Mapped[str] = mapped_column(Text, default="")
    initial_message: Mapped[str] = mapped_column(Text, default="")
    mode: Mapped[RunMode] = mapped_column(_pg_enum(RunMode, "run_mode"), default=RunMode.SINGLE)
    visibility: Mapped[Visibility] = mapped_column(
        _pg_enum(Visibility, "visibility", create_type=False), default=Visibility.PRIVATE
    )
    max_turns: Mapped[int] = mapped_column(Integer, default=12)
    max_tokens: Mapped[int] = mapped_column(Integer, default=50_000)
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    workflow_graph: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    loop_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    work_agents: Mapped[list[WorkAgent]] = relationship(
        back_populates="work", cascade="all, delete-orphan"
    )
    runs: Mapped[list[WorkRun]] = relationship(back_populates="work", cascade="all, delete-orphan")


class WorkAgent(Base):
    __tablename__ = "work_agents"
    __table_args__ = (UniqueConstraint("work_id", "agent_id"),)
    id: Mapped[uuid.UUID] = _uuid_pk()
    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("works.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), index=True
    )
    agent_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_versions.id"), nullable=True
    )
    role_in_work: Mapped[str] = mapped_column(String(80), default="")
    handoff_targets: Mapped[list[str]] = mapped_column(JSONB, default=list)
    order_idx: Mapped[int] = mapped_column(Integer, default=0)

    work: Mapped[Work] = relationship(back_populates="work_agents")


class WorkRun(Base):
    __tablename__ = "work_runs"
    id: Mapped[uuid.UUID] = _uuid_pk()
    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("works.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[RunStatus] = mapped_column(
        _pg_enum(RunStatus, "run_status"), default=RunStatus.PENDING, index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    total_cost: Mapped[float] = mapped_column(Float, default=0.0)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    work: Mapped[Work] = relationship(back_populates="runs")


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[uuid.UUID] = _uuid_pk()
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("work_runs.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id"), nullable=True
    )
    agent_name: Mapped[str] = mapped_column(String(120), default="")
    role: Mapped[str] = mapped_column(String(40), default="assistant")
    content: Mapped[str] = mapped_column(Text)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class LogEntry(Base):
    __tablename__ = "logs"
    id: Mapped[uuid.UUID] = _uuid_pk()
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("work_runs.id", ondelete="CASCADE"), index=True
    )
    level: Mapped[str] = mapped_column(String(16), default="info")
    type: Mapped[str] = mapped_column(String(40), default="event")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Rating(Base):
    __tablename__ = "ratings"
    __table_args__ = (UniqueConstraint("agent_id", "user_id"),)
    id: Mapped[uuid.UUID] = _uuid_pk()
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    stars: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class RagDocument(Base):
    __tablename__ = "rag_documents"
    id: Mapped[uuid.UUID] = _uuid_pk()
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    chunk: Mapped[str] = mapped_column(Text)
    # Vector dim is configurable; use 1024 (Voyage default).
    embedding: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class MemoryEntry(Base):
    __tablename__ = "memory_entries"
    id: Mapped[uuid.UUID] = _uuid_pk()
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    key: Mapped[str] = mapped_column(String(120))
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class CronJob(Base):
    __tablename__ = "cron_jobs"
    id: Mapped[uuid.UUID] = _uuid_pk()
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("works.id", ondelete="CASCADE"), index=True
    )
    cron_expr: Mapped[str] = mapped_column(String(120))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    max_cost_usd: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ArtifactSchedule(Base):
    """Zeitplan für die zeitgesteuerte Selbst-Aktualisierung einer Artefakt-Instanz (Phase 5e).

    Eine Zeile = ein Zeitplan; in v1 genau einer pro Artefakt (UNIQUE(artifact_id)).
    """

    __tablename__ = "artifact_schedules"
    __table_args__ = (UniqueConstraint("artifact_id", name="uq_artifact_schedules_artifact"),)
    id: Mapped[uuid.UUID] = _uuid_pk()
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id", ondelete="CASCADE"), index=True
    )
    cadence: Mapped[ScheduleCadence] = mapped_column(
        _pg_enum(ScheduleCadence, "schedule_cadence"), default=ScheduleCadence.DAILY
    )
    cron_expr: Mapped[str] = mapped_column(String(120))
    refresh_instruction: Mapped[str] = mapped_column(Text, default="")
    completion_mode: Mapped[ScheduleCompletion] = mapped_column(
        _pg_enum(ScheduleCompletion, "schedule_completion"), default=ScheduleCompletion.RECURRING
    )
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[ScheduleStatus] = mapped_column(
        _pg_enum(ScheduleStatus, "schedule_status"), default=ScheduleStatus.ACTIVE
    )
    fail_count: Mapped[int] = mapped_column(Integer, default=0)
    run_count: Mapped[int] = mapped_column(Integer, default=0)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("work_runs.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class ArtifactJob(Base):
    """Ein Job triggert die *bestehende* Instanz zu bestimmten Zeiten (mehrere pro Instanz).

    Löst `ArtifactSchedule` ab. Ein Job erzeugt KEINEN Unter-Agenten — er fährt den
    vorhandenen adjust-Pfad der Instanz mit `instruction`. Felder als String statt PG-Enum,
    um die Migration schlank zu halten; gültige Werte siehe Service `artifact_jobs.py`.
    """

    __tablename__ = "artifact_jobs"
    id: Mapped[uuid.UUID] = _uuid_pk()
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id", ondelete="CASCADE"), index=True
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200), default="")
    instruction: Mapped[str] = mapped_column(Text, default="")
    trigger_kind: Mapped[str] = mapped_column(String(16), default="recurring")  # once|recurring
    cadence: Mapped[str | None] = mapped_column(String(16), nullable=True)  # hourly|daily|weekly
    cron_expr: Mapped[str | None] = mapped_column(String(120), nullable=True)
    run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("work_runs.id", ondelete="SET NULL"), nullable=True
    )
    run_count: Mapped[int] = mapped_column(Integer, default=0)
    fail_count: Mapped[int] = mapped_column(Integer, default=0)
    notify_email: Mapped[bool] = mapped_column(Boolean, default=False)
    notify_telegram: Mapped[bool] = mapped_column(Boolean, default=False)
    notify_chat: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str] = mapped_column(String(16), default="agent")  # agent|user|system
    mode: Mapped[str] = mapped_column(String(20), default="update", server_default="update", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class Template(Base):
    __tablename__ = "templates"
    id: Mapped[uuid.UUID] = _uuid_pk()
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(80), default="", index=True)
    visibility: Mapped[Visibility] = mapped_column(
        _pg_enum(Visibility, "visibility", create_type=False), default=Visibility.PRIVATE
    )
    input_schema: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    output_type: Mapped[TemplateOutput] = mapped_column(
        _pg_enum(TemplateOutput, "template_output"), default=TemplateOutput.HTML
    )
    mode: Mapped[RunMode] = mapped_column(
        _pg_enum(RunMode, "run_mode", create_type=False), default=RunMode.SINGLE
    )
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    max_iterations: Mapped[int] = mapped_column(Integer, default=8)
    max_cost_usd: Mapped[float] = mapped_column(Float, default=1.0)
    success_criteria: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
    publish_status: Mapped[str] = mapped_column(String(16), default="", server_default="")
    publish_note: Mapped[str] = mapped_column(Text, default="", server_default="")


class TemplateRun(Base):
    __tablename__ = "template_runs"
    id: Mapped[uuid.UUID] = _uuid_pk()
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("templates.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    inputs: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("works.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


# pgvector column attached at runtime if pgvector available, otherwise JSON
try:
    from pgvector.sqlalchemy import Vector

    RagDocument.embedding = mapped_column(Vector(1024), nullable=True)  # type: ignore[assignment]
except Exception:
    pass


class Artifact(Base):
    __tablename__ = "artifacts"
    # Phase 5d: kein UNIQUE(owner_id, agent_id) mehr — dieselbe Vorlage/derselbe Agent kann
    # beliebig viele Instanzen (Kontexte) pro Nutzer haben; jede Instanz ist ihre eigene id.
    id: Mapped[uuid.UUID] = _uuid_pk()
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), index=True
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("templates.id", ondelete="SET NULL"), nullable=True
    )
    # Nutzereingaben dieser Instanz (z. B. {"ziel": "Istanbul"}); Quelle für Titel/Refresh.
    inputs: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    title: Mapped[str] = mapped_column(String(200), default="")
    output_type: Mapped[TemplateOutput] = mapped_column(
        _pg_enum(TemplateOutput, "template_output", create_type=False),
        default=TemplateOutput.HTML,
    )
    visibility: Mapped[Visibility] = mapped_column(
        _pg_enum(Visibility, "visibility", create_type=False), default=Visibility.PRIVATE
    )
    # Pro-Instanz-Ausgabevorlage: "prepared:<name>" | "agent" | "slots:<design>".
    output_template: Mapped[str] = mapped_column(String(60), default="", server_default="")
    # Ausgabe-Modus für die nächste Generierung (wie das Ergebnis platziert wird).
    output_mode: Mapped[str] = mapped_column(
        String(16), default="hinzufuegen", server_default="hinzufuegen"
    )
    next_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifacts.id", ondelete="SET NULL"), nullable=True)
    chain_auto: Mapped[bool] = mapped_column(Boolean, default=False)
    chat_summary: Mapped[str] = mapped_column(Text, default="", server_default="")
    summarized_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class ArtifactVersion(Base):
    __tablename__ = "artifact_versions"
    __table_args__ = (
        UniqueConstraint("artifact_id", "version_no", name="uq_artifact_versions_no"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id", ondelete="CASCADE"), index=True
    )
    version_no: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text, default="")
    data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    prompt: Mapped[str] = mapped_column(Text, default="")
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("work_runs.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ArtifactMessage(Base):
    """Persistenter Chat-Thread je Instanz (Dialog-Agent). Assistant-`content` ist nur
    die Prosa; das Canvas-HTML lebt in `artifact_versions` (verknüpft via `version_id`)."""

    __tablename__ = "artifact_messages"
    id: Mapped[uuid.UUID] = _uuid_pk()
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, default="")
    version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifact_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    file_ids: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ArtifactFile(Base):
    """Vom Nutzer im Instanz-Chat hochgeladene Datei (Bilder fürs HTML / Dokumente).
    Liegt unter MEDIA_ROOT/artifacts/{owner}/{artifact}/ neben der HTML; `url` ist der
    öffentliche /media/…-Pfad. Was der Agent damit tut, entscheidet der Dialog."""

    __tablename__ = "artifact_files"
    id: Mapped[uuid.UUID] = _uuid_pk()
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id", ondelete="CASCADE"), index=True
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255), default="")
    url: Mapped[str] = mapped_column(String(512), default="")
    content_type: Mapped[str] = mapped_column(String(100), default="")
    size: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ArtifactConnection(Base):
    """Verschlüsselte Veröffentlichungs-Verbindung pro Instanz (kind-agnostisch).
    `config` enthält alle nicht-geheimen Felder (z. B. host, port, username, remote_path);
    `secret_encrypted` hält genau ein Fernet-verschlüsseltes Geheimnis (Passwort/Token)."""

    __tablename__ = "artifact_connections"
    __table_args__ = (UniqueConstraint("artifact_id", "kind", name="uq_artifact_connection_kind"),)
    id: Mapped[uuid.UUID] = _uuid_pk()
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id", ondelete="CASCADE"), index=True
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(80), default="sftp")
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    secret_encrypted: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class WalletLedger(Base):
    __tablename__ = "wallet_ledger"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(16))  # "topup" | "charge"
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6))  # signiert (+topup, -charge)
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    provider_cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0"))
    margin: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("1.25"))
    description: Mapped[str] = mapped_column(String(200), default="")
    external_ref: Mapped[str | None] = mapped_column(String(120), nullable=True, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ModelPrice(Base):
    __tablename__ = "model_price"

    id: Mapped[uuid.UUID] = _uuid_pk()
    provider: Mapped[str] = mapped_column(String(16))  # "anthropic" | "openai"
    model: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(80), default="")
    input_per_million_usd: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0"))
    output_per_million_usd: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)


class McpServer(Base):
    """Kuratierter MCP-Server-Katalog (vom Admin verwaltet). Enthält KEINE Geheimnisse —
    Zugangsdaten leben pro Instanz verschlüsselt in artifact_connections."""

    __tablename__ = "mcp_server"
    id: Mapped[uuid.UUID] = _uuid_pk()
    server_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    description: Mapped[str] = mapped_column(String(512), default="")
    transport: Mapped[str] = mapped_column(String(20), default="streamable_http")
    url: Mapped[str] = mapped_column(String(512), default="")
    requires_credential: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    auth_header: Mapped[str] = mapped_column(
        String(80), default="Authorization", server_default="Authorization"
    )
    auth_value_template: Mapped[str] = mapped_column(
        String(200), default="Bearer {secret}", server_default="Bearer {secret}"
    )
    secret_label: Mapped[str] = mapped_column(
        String(120), default="Token / API-Key", server_default="Token / API-Key"
    )


class ChannelSession(Base):
    __tablename__ = "channel_sessions"
    id: Mapped[uuid.UUID] = _uuid_pk()
    channel: Mapped[str] = mapped_column(String(20))
    channel_user_id: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True)
    active_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifacts.id", ondelete="SET NULL"), nullable=True)
    pending: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    __table_args__ = (UniqueConstraint("channel", "channel_user_id", name="uq_channel_user"),)
