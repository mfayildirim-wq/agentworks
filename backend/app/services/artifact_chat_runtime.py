"""Produktiver LLM-Aufruf für einen Dialog-Turn.

Baut aus der aktuellen Agent-Version (Modell/Provider) + dem Key des
**Agent-Eigentümers** (Template-Autor) einen Ein-Schuss-`complete(system, message)`.
In Tests wird `complete` gefälscht; hier ist die echte AutoGen-Anbindung.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from agent_runtime.executor import ExecutorContext
from agent_runtime.mcp_tools import load_mcp_tools_session
from agent_runtime.model_client import (
    make_model_client,
    provider_supports_tools,
    provider_supports_vision,
)
from agent_runtime.spec import AgentSpec
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import crypto
from app.core.settings import get_settings
from app.db.models import Agent, AgentVersion, Artifact, ArtifactFile, ArtifactMessage, Template, User
from app.services import artifact_connections, mcp_catalog
from app.services.agent_tools import (
    build_tools,
    publish_etiquette,
    scheduling_etiquette,
    slot_etiquette,
    slot_tools,
    tool_capability_note,
)
from app.services import system_keys
from app.services.artifact_files import _disk_path

settings = get_settings()

_MAX_VISION_IMAGES = 4
_MAX_VISION_BYTES = 5 * 1024 * 1024


async def _latest_turn_image_paths(db: AsyncSession, artifact_id: UUID) -> list[str]:
    """Plattenpfade der Bilder, die am LETZTEN User-Turn mit Anhängen hingen.

    Leere Liste, wenn der letzte anhang-tragende User-Turn keine Bilder hatte oder
    die Dateien fehlen. Begrenzt auf _MAX_VISION_IMAGES, überspringt > _MAX_VISION_BYTES.
    """
    rows = await db.execute(
        select(ArtifactMessage)
        .where(ArtifactMessage.artifact_id == artifact_id, ArtifactMessage.role == "user")
        .order_by(ArtifactMessage.created_at.desc(), ArtifactMessage.id.desc())
    )
    file_ids: list[str] = []
    for m in rows.scalars().all():
        if m.file_ids:
            file_ids = m.file_ids
            break
    if not file_ids:
        return []

    ids = [UUID(x) for x in file_ids]
    frows = await db.execute(select(ArtifactFile).where(ArtifactFile.id.in_(ids)))
    paths: list[str] = []
    for f in frows.scalars().all():
        if not (f.content_type or "").startswith("image/"):
            continue
        if f.size > _MAX_VISION_BYTES:
            continue
        try:
            disk = _disk_path(f.url)
        except ValueError:
            continue
        if Path(disk).exists():
            paths.append(disk)
        if len(paths) >= _MAX_VISION_IMAGES:
            break
    return paths


def _build_user_message(text: str, image_paths: list[str]) -> "TextMessage | MultiModalMessage":
    """Baut die User-Nachricht: reiner Text, oder multimodal (Text + Bilder)."""
    from autogen_agentchat.messages import MultiModalMessage, TextMessage

    if not image_paths:
        return TextMessage(content=text, source="user")

    from autogen_core import Image

    images = [Image.from_file(Path(p)) for p in image_paths]
    return MultiModalMessage(content=[text, *images], source="user")


def _safe_name(name: str) -> str:
    # AutoGen stellt ZWEI Anforderungen an den Agent-Namen (message.source):
    #  1. der Basis-Agent verlangt einen gültigen Python-Identifier (str.isidentifier())
    #     → KEINE Bindestriche, kein führender Ziffer.
    #  2. der Anthropic-Client erlaubt nur ASCII [A-Za-z0-9_]
    #     → Vorsicht: Pythons isalnum()/isidentifier() sind True für Unicode-Buchstaben
    #       (Umlaute ä/ö/ü), die müssen ebenfalls ersetzt werden.
    # Daher: nur ASCII-alnum + Unterstrich behalten, Rest → "_"; führende Ziffer absichern.
    cleaned = "".join(
        c if c.isascii() and (c.isalnum() or c == "_") else "_" for c in name
    )
    if not cleaned:
        return "agent"
    if cleaned[0].isdigit():
        cleaned = "a_" + cleaned
    return cleaned


async def _mcp_tools_for_artifact(
    db: AsyncSession, artifact_id: UUID, exit_stack: AsyncExitStack
) -> list:
    """Lädt die MCP-Tools, die das Template dieser Instanz per Allowlist erlaubt.

    Credential-lose Server direkt; credential-pflichtige nur, wenn die Instanz
    einen Token hinterlegt hat (Header-Injektion). Fehlertolerant: ein nicht
    erreichbarer Server liefert [] und blockt den Turn nicht.

    Jede SSE-Session bleibt über den `exit_stack` für den gesamten Turn offen,
    damit Tool-Aufrufe über dieselbe Verbindung laufen (kein Reconnect pro Aufruf).
    """
    art = await db.get(Artifact, artifact_id)
    if art is None or art.template_id is None:
        return []
    tpl = await db.get(Template, art.template_id)
    if tpl is None:
        return []
    ids = (tpl.config or {}).get("mcp_servers") or []
    tools: list = []
    for sid in ids:
        entry = await mcp_catalog.get(db, sid)
        if entry is None or not entry.enabled:
            continue
        headers = None
        if entry.requires_credential:
            try:
                conn = await artifact_connections.get_connection(
                    db, artifact_id, art.owner_id, f"mcp:{entry.server_id}"
                )
                if conn is None or not conn.secret_encrypted:
                    continue  # Token noch nicht hinterlegt → Server überspringen
                secret = crypto.decrypt(conn.secret_encrypted)
                headers = {entry.auth_header: entry.auth_value_template.format(secret=secret)}
            except Exception:  # noqa: BLE001 — defekter Token darf den Turn nicht abbrechen
                continue
        server_tools = await exit_stack.enter_async_context(
            load_mcp_tools_session(entry.url, entry.transport, headers=headers)
        )
        tools.extend(server_tools)
    return tools


async def _output_mode_for(db: AsyncSession, artifact_id: UUID) -> tuple[str, list[dict]]:
    """Ausgabe-Modus der Instanz nach `output_template` (mode, placeholders).

    Delegiert an den gemeinsamen Resolver in artifact_chat, damit Prompt-Bau und
    Tool-Entscheidung dieselbe Quelle nutzen."""
    from app.services.artifact_chat import _output_mode_for as _resolve

    art = await db.get(Artifact, artifact_id)
    if art is None:
        return "html", []
    return await _resolve(db, art)


async def _content_mode_for(db: AsyncSession, artifact_id: UUID) -> str:
    """content_mode ('html' | 'slots') der Instanz — nach `output_template` aufgelöst."""
    mode, _ = await _output_mode_for(db, artifact_id)
    return mode


async def _publish_tools_for_artifact(db: AsyncSession, artifact_id: UUID) -> list:
    """Sammelt Veröffentlichungs-Tools gemäß `publish_targets` des Templates der Instanz."""
    art = await db.get(Artifact, artifact_id)
    if art is None or art.template_id is None:
        return []
    tpl = await db.get(Template, art.template_id)
    if tpl is None:
        return []
    targets = (tpl.config or {}).get("publish_targets") or []
    from app.services.agent_tools import publish_tools, wordpress_tools

    out: list = []
    if "sftp" in targets:
        out += publish_tools(artifact_id=artifact_id, owner_id=art.owner_id)
    if "wordpress" in targets:
        out += wordpress_tools(artifact_id=artifact_id, owner_id=art.owner_id)
    if "google_calendar" in targets:
        from app.services.agent_tools import google_calendar_tools
        out += google_calendar_tools(artifact_id=artifact_id, owner_id=art.owner_id)
    if "gmail" in targets:
        from app.services.agent_tools import gmail_tools
        out += gmail_tools(artifact_id=artifact_id, owner_id=art.owner_id)
    return out


@dataclass
class TurnUsage:
    model: str
    owner_id: UUID
    tokens_in: int = 0
    tokens_out: int = 0


async def make_completer(
    db: AsyncSession, artifact_id: UUID
) -> tuple[Callable[[str, str], Awaitable[str]], TurnUsage]:
    """Löst Modell/Provider/Key des Agent-Eigentümers auf und liefert `(complete, meta)`.

    `meta` (TurnUsage) sammelt die Token-Nutzung des Turns (vom Modell-Client),
    sodass der Aufrufer danach abrechnen kann.
    """
    art = await db.get(Artifact, artifact_id)
    if art is None:
        raise ValueError(f"artifact {artifact_id} fehlt")
    agent = await db.get(Agent, art.agent_id)
    if agent is None or agent.current_version_id is None:
        raise ValueError("agent oder aktuelle Version fehlt")
    version = await db.get(AgentVersion, agent.current_version_id)
    if version is None:
        raise ValueError("agent-version fehlt")

    # Provider aus dem Modell ableiten (Modell = Wahrheitsquelle) — verhindert Fehlrouting,
    # wenn das provider-Feld am Agenten veraltet ist (z.B. "ollama" + Cloud-Modell).
    from app.services import model_pricing

    provider = await model_pricing.provider_for(db, version.model) or getattr(
        version, "provider", "anthropic"
    )
    key = (
        crypto.decrypt(agent.api_key_encrypted)
        if agent.api_key_encrypted
        else await system_keys.system_key_for(db, provider)
    )
    spec = AgentSpec(
        id=agent.id,
        name=agent.name,
        system_prompt="",
        model=version.model,
        provider=provider,
        api_key=key,
    )
    meta = TurnUsage(model=version.model, owner_id=art.owner_id)
    ctx = ExecutorContext(
        api_key=settings.anthropic_api_key,
        on_event=lambda _e: None,
        ollama_url=settings.ollama_url,
    )
    safe = _safe_name(agent.name)

    tool_capable = provider_supports_tools(provider)
    tools = (
        build_tools(artifact_id=artifact_id, owner_id=art.owner_id, allow_scheduling=True)
        if tool_capable
        else []
    )
    note = tool_capability_note(tool_capable) + (scheduling_etiquette() if tool_capable else "")

    publish_extra = await _publish_tools_for_artifact(db, artifact_id) if tool_capable else []
    if publish_extra:
        tools = list(tools) + publish_extra
        note = note + publish_etiquette()

    # Bild-Werkzeug für alle tool-fähigen Agenten (der Prompt entscheidet die Nutzung).
    if tool_capable:
        from app.services.agent_tools import image_tools
        tools = list(tools) + image_tools(artifact_id=artifact_id, owner_id=art.owner_id)

    content_mode, placeholders = await _output_mode_for(db, artifact_id)
    if tool_capable and content_mode == "slots":
        tools = list(tools) + slot_tools(artifact_id=artifact_id, owner_id=art.owner_id)
        note = note + slot_etiquette()
        if placeholders:
            from app.services.artifact_chat import prepared_slot_note

            note = note + prepared_slot_note(placeholders)

    # MCP-Sessions müssen für den gesamten Turn offen bleiben. Sie werden ERST in
    # complete() geöffnet (innerhalb des try) und im finally geschlossen — so sind
    # Öffnen und Schließen untrennbar (kein Leak, falls complete nie aufgerufen wird).
    _mcp_stack = AsyncExitStack()

    vision_paths = (
        await _latest_turn_image_paths(db, artifact_id)
        if provider_supports_vision(provider)
        else []
    )

    async def complete(system: str, message: str) -> str:
        from autogen_agentchat.agents import AssistantAgent
        from autogen_core import CancellationToken

        client = make_model_client(spec, ctx)
        try:
            turn_tools = list(tools)
            if tool_capable:
                turn_tools += await _mcp_tools_for_artifact(db, artifact_id, _mcp_stack)
            ai = AssistantAgent(
                name=safe,
                model_client=client,
                system_message=note + system,
                tools=turn_tools or None,
                reflect_on_tool_use=bool(turn_tools),
                # Mehrere Tool-Runden pro Turn: sonst kündigt der Agent den nächsten
                # Tool-Aufruf nur an (z.B. „Account gefunden, lade jetzt Repos…") und
                # beendet den Turn. Erlaubt Tool-Ketten (get_me → list_repos → Antwort).
                max_tool_iterations=8 if turn_tools else 1,
            )
            res = await ai.on_messages(
                [_build_user_message(message, vision_paths)], CancellationToken()
            )
            try:
                # total_usage() ist der KUMULATIVE Verbrauch dieses Client-Objekts über
                # ALLE internen LLM-Aufrufe von on_messages (inkl. der bis zu 8 Tool-Runden).
                # Da pro Turn genau ein Client erzeugt wird, ist das die Gesamt-Nutzung des
                # Turns — wichtig für die Abrechnung von Tool-lastigen Läufen (MCP/GitHub).
                u = client.total_usage()
                meta.tokens_in += int(getattr(u, "prompt_tokens", 0) or 0)
                meta.tokens_out += int(getattr(u, "completion_tokens", 0) or 0)
            except Exception:
                pass
            return res.chat_message.content if res.chat_message else ""
        finally:
            await client.close()
            await _mcp_stack.aclose()

    return complete, meta
