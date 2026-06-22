from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.models import RunMode, TemplateOutput, Visibility


class TemplateInputField(BaseModel):
    key: str = Field(min_length=1, max_length=60)
    label: str = Field(min_length=1, max_length=120)
    type: Literal["string", "number", "select", "boolean"] = "string"
    required: bool = False
    default: Any | None = None
    options: list[str] | None = None


class TemplateCommand(BaseModel):
    """Template-eigene „/"-Funktion: Slash-Name + Anweisung + Platzierung (Modus)."""

    key: str = Field(pattern=r"^[a-z0-9_-]{1,30}$")
    label: str = Field(min_length=1, max_length=60)
    instruction: str = Field(min_length=1, max_length=2000)
    mode: str = Field(max_length=16)


class TemplateConfig(BaseModel):
    agent_ids: list[UUID] = Field(default_factory=list)
    prompt_template: str = ""
    # Gewählte eingebaute HTML-Vorlage (Schritt ①.1); "" = keine/Altbestand.
    html_template_id: str = ""
    mcp_servers: list[str] = Field(default_factory=list)
    publish_targets: list[str] = Field(default_factory=list)
    # Inhaltsmodus: "html" (HTML-Canvas-Kontrakt) | "slots" (Slot-Werkzeuge).
    content_mode: str = "html"
    default_output_mode: str = ""
    # Template-eigene „/"-Funktionen (Feature 2); leer = nur System-Befehle.
    commands: list[TemplateCommand] = Field(default_factory=list)


class HtmlTemplateOut(BaseModel):
    """Eine eingebaute HTML-Vorlage inkl. vollem HTML für die Live-Vorschau im Frontend."""

    id: str
    name: str
    description: str
    html: str
    # Reines CSS der Vorlage (Inhalt von <style>…</style>, ohne Tags) für den Vue-Canvas-Iframe.
    css: str = ""


class TemplateCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    category: str = Field(default="", max_length=80)
    visibility: Visibility = Visibility.PRIVATE
    input_schema: list[TemplateInputField] = Field(default_factory=list)
    output_type: TemplateOutput = TemplateOutput.HTML
    mode: RunMode = RunMode.SINGLE
    config: TemplateConfig = Field(default_factory=TemplateConfig)
    max_iterations: int = Field(default=8, ge=1, le=50)
    max_cost_usd: float = Field(default=1.0, gt=0)
    success_criteria: list[str] | None = None
    image_url: str | None = None


class TemplateUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    category: str | None = Field(default=None, max_length=80)
    visibility: Visibility | None = None
    input_schema: list[TemplateInputField] | None = None
    output_type: TemplateOutput | None = None
    mode: RunMode | None = None
    config: TemplateConfig | None = None
    max_iterations: int | None = Field(default=None, ge=1, le=50)
    max_cost_usd: float | None = Field(default=None, gt=0)
    success_criteria: list[str] | None = None
    image_url: str | None = None


class TemplateOut(BaseModel):
    id: UUID
    owner_id: UUID
    title: str
    description: str
    category: str
    visibility: Visibility
    input_schema: list[TemplateInputField]
    output_type: TemplateOutput
    mode: RunMode
    config: TemplateConfig
    max_iterations: int
    max_cost_usd: float
    success_criteria: list[str] | None
    image_url: str | None
    # Modell des primären Agenten (config.agent_ids[0]); None, wenn nicht auflösbar.
    model: str | None = None
    publish_status: str = ""
    publish_note: str = ""
    # Aggregierte Marktplatz-Kennzahlen (in get_template berechnet).
    avg_stars: float = 0
    ratings_count: int = 0
    works_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True, "protected_namespaces": ()}


class PublicTemplateOut(BaseModel):
    """Schlanke, tokenfreie Sicht für die öffentliche Startseite (Marktplatz)."""

    id: UUID
    title: str
    description: str
    category: str
    image_url: str | None
    output_type: TemplateOutput
    # Modell des primären Agenten (config.agent_ids[0]); None, wenn nicht auflösbar.
    model: str | None = None
    # Richtpreis pro Lauf (= max_cost_usd des Templates).
    price: float
    # Aggregierte Marktplatz-Kennzahlen (Sterne des primären Agenten, Zahl der Instanzen).
    avg_stars: float = 0
    ratings_count: int = 0
    works_count: int = 0
    # Ersteller (Creator) der Vorlage — für Profilbild/Name auf der Karte + Profil-Link.
    creator_id: UUID | None = None
    creator_name: str = ""
    creator_avatar: str | None = None

    model_config = {"protected_namespaces": ()}


class AgentTemplateCreate(BaseModel):
    """Einheitliche „Agent-Vorlage": ein Formular für Name, Prompt, Modell, Kosten.

    Erzeugt unter der Haube atomar einen Agenten (Modell + System-Prompt) und ein
    Template, das ihn umhüllt. Eingaben holt später der Chat (Schritt 2) — daher
    kein input_schema hier.
    """

    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    prompt: str = Field(min_length=1, max_length=8000)
    # Standard: lokales, kostenloses Modell (läuft ohne bezahlten API-Key).
    # Claude/OpenAI sind wählbar, sobald ein gültiger Key hinterlegt ist.
    model: str = Field(default="qwen2.5:3b", max_length=80)
    price: float = Field(default=1.0, gt=0)
    category: str = Field(min_length=1, max_length=80)
    visibility: Visibility = Visibility.PUBLIC
    image_url: str | None = None
    # Pflicht-Auswahl einer eingebauten HTML-Vorlage; gegen html_templates validiert.
    html_template_id: str = Field(default="", max_length=40)
    mcp_servers: list[str] = Field(default_factory=list)
    publish_targets: list[str] = Field(default_factory=list)
    content_mode: str = Field(default="html", max_length=10)
    default_output_mode: str = Field(default="", max_length=16)
    commands: list[TemplateCommand] = Field(default_factory=list)


class AgentTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    prompt: str | None = Field(default=None, min_length=1, max_length=8000)
    model: str | None = Field(default=None, max_length=80)
    price: float | None = Field(default=None, gt=0)
    category: str | None = Field(default=None, max_length=80)
    visibility: Visibility | None = None
    image_url: str | None = None
    html_template_id: str | None = Field(default=None, max_length=40)
    mcp_servers: list[str] | None = None
    content_mode: str | None = None
    default_output_mode: str | None = Field(default=None, max_length=16)
    commands: list[TemplateCommand] | None = None


class InstantiateRequest(BaseModel):
    inputs: dict[str, Any] = Field(default_factory=dict)
    # Pro-Instanz-Ausgabevorlage: "prepared:<name>" | "agent" | "slots:<design>".
    # "" -> Service waehlt eine zufaellige prepared-Vorlage als Default.
    output_template: str = ""


class InstantiateResponse(BaseModel):
    template_run_id: UUID
    work_id: UUID
    # None bei konversationellen Instanzen (kein Auto-Generierungslauf; Canvas via Dialog).
    run_id: UUID | None = None
    # Neu erzeugte Instanz (Phase 5d); Frontend leitet auf /artifacts/{artifact_id}.
    artifact_id: UUID | None = None
