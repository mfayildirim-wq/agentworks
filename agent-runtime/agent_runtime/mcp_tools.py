"""Lädt Tools eines MCP-Servers (HTTP/SSE) als AutoGen-Tools.

WICHTIG: SSE-Verbindungen müssen für die gesamte Dauer eines Turns offen bleiben.
`load_mcp_tools_session` ist ein Async-Context-Manager, der die Session hält und
Tools gebunden an die Session liefert — nur so können Tool-Aufrufe gelingen.

Der Verbindungs-Timeout gilt nur für die Initialisierung; danach bleibt die
Session ohne Timeout für den gesamten Agentenaufruf (typisch < 60 s) offen.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

logger = logging.getLogger(__name__)


def _params(url: str, transport: str, headers: dict[str, str] | None = None):
    from autogen_ext.tools.mcp import SseServerParams, StreamableHttpServerParams

    if transport == "streamable_http":
        return StreamableHttpServerParams(url=url, headers=headers)
    return SseServerParams(url=url, headers=headers)


def _describe_exc(exc: BaseException) -> str:
    """Entpackt (verschachtelte) ExceptionGroups zur echten Ursache.

    Loggt nur Fehlertyp + Kurztext der Blatt-Exceptions (z.B. „HTTPStatusError: 401 …"),
    nie Header/Token — die liegen in den Request-Params, nicht in der Antwort-Meldung."""
    leaves: list[str] = []

    def walk(e: BaseException) -> None:
        subs = getattr(e, "exceptions", None)
        if subs:
            for s in subs:
                walk(s)
        else:
            leaves.append(f"{type(e).__name__}: {str(e)[:160]}")

    walk(exc)
    return " | ".join(leaves) or type(exc).__name__


def _sanitize_json_schema(node):
    """Glättet JSON-Schemas für autogen 0.7.5: `type`-Unions (z.B. ["string","null"])
    → einzelner Typ. autogens schema_to_pydantic_model nutzt den Typ als Dict-Key und
    wirft sonst `TypeError: unhashable type: 'list'` (viele echte MCPs wie GitHub liefern
    nullable Felder als Typ-Listen)."""
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if k == "type" and isinstance(v, list):
                non_null = [t for t in v if t != "null"]
                out[k] = non_null[0] if non_null else "string"
            else:
                out[k] = _sanitize_json_schema(v)
        return out
    if isinstance(node, list):
        return [_sanitize_json_schema(x) for x in node]
    return node


_schema_patch_done = False


def _ensure_schema_patch() -> None:
    """Wickelt autogens schema_to_pydantic_model einmalig so ein, dass Tool-Schemas
    vorher gesäubert werden — sonst scheitern MCPs mit Typ-Unions beim Tool-Laden."""
    global _schema_patch_done
    if _schema_patch_done:
        return
    _schema_patch_done = True
    try:
        from autogen_ext.tools.mcp import _base as _b

        _orig = _b.schema_to_pydantic_model

        def _patched(schema, *args, **kwargs):
            try:
                schema = _sanitize_json_schema(schema)
            except Exception:  # noqa: BLE001 — Sanitizer darf nie den Ladevorgang brechen
                pass
            return _orig(schema, *args, **kwargs)

        _b.schema_to_pydantic_model = _patched
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning("mcp-schema-patch-failed err=%s", type(exc).__name__)


@asynccontextmanager
async def load_mcp_tools_session(
    url: str,
    transport: str = "sse",
    headers: dict[str, str] | None = None,
    timeout: float = 15.0,
) -> AsyncGenerator[list, None]:
    """Async-Context-Manager: öffnet eine MCP-Session, hält sie offen und liefert
    die an die Session gebundenen Tools.

    Die Session bleibt für den gesamten `async with`-Block aktiv, sodass
    Tool-Aufrufe über dieselbe Verbindung laufen (kein Reconnect pro Aufruf).
    Bei Verbindungs-/Protokollfehlern wird eine leere Liste geliefert (best-effort).
    """
    from autogen_ext.tools.mcp import create_mcp_server_session, mcp_server_tools

    _ensure_schema_patch()
    params = _params(url, transport, headers)
    try:
        async with create_mcp_server_session(params) as session:
            # Nur Initialisierung mit Timeout schützen; danach läuft die Session
            # für den gesamten Turn ohne zusätzlichen Zeitbegrenzer.
            await asyncio.wait_for(session.initialize(), timeout=timeout)
            tools = await asyncio.wait_for(
                mcp_server_tools(server_params=params, session=session), timeout=timeout
            )
            yield tools
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning("mcp-session-failed url=%s err=%s", url, _describe_exc(exc))
        yield []

