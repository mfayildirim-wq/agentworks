from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.models import (
    ScheduleCadence,
    ScheduleCompletion,
    ScheduleStatus,
    TemplateOutput,
    Visibility,
)


class ArtifactVersionOut(BaseModel):
    id: UUID
    version_no: int
    prompt: str
    run_id: UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class JobOut(BaseModel):
    id: UUID
    artifact_id: UUID
    title: str
    instruction: str
    trigger_kind: str
    cadence: str | None = None
    status: str
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    run_count: int
    fail_count: int
    notify_email: bool | None = False
    notify_telegram: bool | None = False
    notify_chat: bool | None = False
    created_by: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RecentAction(BaseModel):
    prompt: str
    created_at: datetime


class McpCredentialNeed(BaseModel):
    server_id: str
    name: str
    secret_label: str
    configured: bool


class ChainNode(BaseModel):
    id: UUID
    title: str
    image_url: str | None = None
    is_self: bool = False


class ArtifactView(BaseModel):
    id: UUID
    owner_id: UUID
    agent_id: UUID
    template_id: UUID | None = None
    inputs: dict = Field(default_factory=dict)
    title: str
    output_type: TemplateOutput
    visibility: Visibility
    # Agent-/Vorlagen-Bild (emoji:… | preset:… | /media/… ) für den Chat-Dialog.
    image_url: str | None = None
    current_content: str = ""
    current_version_no: int | None = None
    versions: list[ArtifactVersionOut] = Field(default_factory=list)
    jobs: list[JobOut] = Field(default_factory=list)
    publish_targets: list[str] = Field(default_factory=list)
    mcp_credentials: list[McpCredentialNeed] = Field(default_factory=list)
    # Inhaltsmodus der Vorlage: "html" (HTML-Canvas) | "slots" (Slot-Werkzeuge).
    content_mode: str = "html"
    # Gewähltes Design der Vorlage (für die Vue-Theme-Auswahl im Frontend); "" = Standard.
    html_template_id: str = ""
    # Gewähltes Ausgabe-Template dieser Instanz: prepared:<name> | agent | slots:<design> | "".
    output_template: str = ""
    # Öffentliche URL des externen Ziels (z.B. veröffentlichter WP-Beitrag) für die
    # rechte Live-Vorschau; None, wenn kein externes Ziel / nicht der Eigentümer.
    external_url: str | None = None
    updated_at: datetime
    # Aufgelaufene Abrechnungskosten dieser Instanz (Σ Charges).
    cost_total_usd: Decimal = Decimal("0")
    # true, wenn der anfragende Nutzer Eigentümer ist (gating der Sichtbarkeits-Auswahl im Frontend).
    is_owner: bool = False
    # Eigene Bewertung des Agenten dieser Instanz (0 = noch nicht bewertet) + Aggregat,
    # damit das Bewerten-Sternecontrol im Frontend ohne Extra-Aufruf vorbelegt ist.
    my_stars: int = 0
    agent_rating_avg: float = 0
    agent_rating_count: int = 0
    chain_next_id: UUID | None = None
    chain_auto: bool = False
    chain_path: list[ChainNode] = Field(default_factory=list)
    # Ausgabe-Modus für die nächste Generierung (wie das Ergebnis platziert wird).
    output_mode: str = "ueberschreiben"


class MasterInstance(BaseModel):
    id: UUID
    title: str
    # Agent-/Vorlagen-Bild (emoji:… | preset:… | /media/… ) für die Master-Nav-Leiste.
    image_url: str | None = None
    updated_at: datetime | None = None
    # Gerendertes HTML-Ergebnis dieser Instanz (current_version.content).
    html: str
    # True, wenn die Instanz mindestens eine aktive zeitgesteuerte Aufgabe hat (Uhr-Icon).
    scheduled: bool = False


class MasterPage(BaseModel):
    owner_id: UUID
    owner_name: str
    is_owner: bool
    instances: list[MasterInstance] = Field(default_factory=list)


class ArtifactListItem(BaseModel):
    id: UUID
    owner_id: UUID
    agent_id: UUID
    template_id: UUID | None = None
    inputs: dict = Field(default_factory=dict)
    title: str
    agent_name: str = ""
    visibility: Visibility
    # Agent-/Vorlagen-Bild (emoji:… | preset:… | /media/… ) fürs Dashboard.
    image_url: str | None = None
    current_version_no: int | None = None
    # Aktuelles HTML-Ergebnis (für die Output-Vorschau im Dashboard); None = noch leer.
    preview_html: str | None = None
    updated_at: datetime
    # Zeitplan-Status (5e): Cadence des aktiven Selbst-Updates, sonst None.
    schedule_cadence: str | None = None
    job_count: int = 0
    recent_actions: list[RecentAction] = Field(default_factory=list)
    # Modell des Agenten + ob der Lauf auf dem eigenen API-Key des Nutzers läuft.
    model: str | None = None
    uses_own_key: bool = False


class SharedArtifactOut(BaseModel):
    artifact_id: UUID
    title: str
    icon: str | None = None
    owner_name: str
    visibility: str
    updated_at: datetime
    template_title: str | None = None


class AdjustRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=2000)


class AdjustResponse(BaseModel):
    run_id: UUID


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    file_ids: list[UUID] = Field(default_factory=list)


class ArtifactFileOut(BaseModel):
    id: UUID
    filename: str
    url: str
    content_type: str
    size: int
    created_at: datetime
    model_config = {"from_attributes": True}


class ArtifactMessageOut(BaseModel):
    id: UUID
    role: str
    content: str
    version_id: UUID | None = None
    # version_no der erzeugten Seite (für Inline-Marker „Seite aktualisiert (v{n})").
    version_no: int | None = None
    created_at: datetime


class SlotPut(BaseModel):
    title: str | None = None
    body: str | None = Field(default=None, max_length=200_000)
    type: str = "richtext"
    order: int | None = None


class LayoutPut(BaseModel):
    layout: str


class ChainSetIn(BaseModel):
    next_artifact_id: UUID | None = None
    auto: bool = False


class OutputModeIn(BaseModel):
    mode: str


class ConnectionPut(BaseModel):
    config: dict = Field(default_factory=dict)
    secret: str = Field(default="", max_length=2048)  # leer bei Update = unverändert


class ConnectionOut(BaseModel):
    kind: str
    config: dict
    configured: bool


class PublishResult(BaseModel):
    ok: bool
    message: str


class SchedulePut(BaseModel):
    cadence: ScheduleCadence
    refresh_instruction: str = Field(min_length=1, max_length=2000)
    enabled: bool = True
    completion_mode: ScheduleCompletion = ScheduleCompletion.RECURRING
    end_at: datetime | None = None


class ScheduleOut(BaseModel):
    id: UUID
    artifact_id: UUID
    cadence: ScheduleCadence
    cron_expr: str
    refresh_instruction: str
    completion_mode: ScheduleCompletion
    end_at: datetime | None = None
    enabled: bool
    status: ScheduleStatus
    fail_count: int
    run_count: int
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    updated_at: datetime

    model_config = {"from_attributes": True}
