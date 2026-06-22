"""Rollende Zusammenfassung (Summary-Buffer) für den Chat-Turn-Input.

Hält die letzten `KEEP_RECENT` Nachrichten wörtlich; faltet ältere — erst wenn die
noch nicht zusammengefassten `MAX_BUFFER` übersteigen — in eine laufende Zusammenfassung
(Haiku). So bleibt der Turn-Input klein, ohne jeden Turn ein Summarize-LLM zu brauchen."""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.core.settings import get_settings

settings = get_settings()

KEEP_RECENT = 6
MAX_BUFFER = 14


def _compose(messages: list) -> str:
    lines = []
    for m in messages:
        who = "Nutzer" if m.role == "user" else "Agent"
        lines.append(f"{who}: {m.content}")
    return "\n".join(lines)


def select_window(messages: list, summarized_count: int,
                  keep_recent: int = KEEP_RECENT, max_buffer: int = MAX_BUFFER):
    """(to_fold, recent, new_summarized_count). Faltet nur bei Überlauf > max_buffer."""
    n = len(messages)
    over = n - summarized_count
    if over > max_buffer:
        cut = n - keep_recent
        return messages[summarized_count:cut], messages[cut:], cut
    return [], messages[summarized_count:], summarized_count


def build_turn_input(chat_summary: str, recent: list) -> str:
    body = _compose(recent)
    if chat_summary:
        return f"Bisheriger Verlauf (Zusammenfassung):\n{chat_summary}\n\n{body}"
    return body


async def summarize(prev_summary: str, to_fold: list) -> str:
    """Faltet `to_fold` in `prev_summary` (Haiku, Plattform-Key). Defensiv: bei Fehler
    bleibt die alte Zusammenfassung erhalten."""
    if not to_fold:
        return prev_summary or ""
    from uuid import uuid4

    from autogen_core.models import UserMessage
    from agent_runtime.executor import ExecutorContext
    from agent_runtime.model_client import make_model_client
    from agent_runtime.spec import AgentSpec

    prompt = (
        "Hier ist die bisherige Zusammenfassung des Gesprächs:\n"
        f"{prev_summary or '(keine)'}\n\n"
        "Neue Nachrichten:\n"
        f"{_compose(to_fold)}\n\n"
        "Aktualisiere die Zusammenfassung KNAPP auf Deutsch (Fakten, getroffene "
        "Entscheidungen, offene Punkte; max. ~1500 Zeichen). Gib NUR die aktualisierte "
        "Zusammenfassung aus, ohne Vorrede."
    )
    spec = AgentSpec(id=uuid4(), name="summarizer", system_prompt="",
                     model="claude-haiku-4-5", provider="anthropic",
                     api_key=settings.anthropic_api_key)
    ctx = ExecutorContext(api_key=settings.anthropic_api_key, on_event=lambda _e: None,
                          ollama_url=settings.ollama_url)
    client = make_model_client(spec, ctx)
    try:
        res = await client.create([UserMessage(content=prompt, source="user")])
        out = res.content if isinstance(res.content, str) else None
        return (out or prev_summary or "").strip()[:2000]
    except Exception:
        return prev_summary or ""
    finally:
        await client.close()


async def summarize_output(source_title: str, content: str) -> str:
    """Verdichtet den (ggf. HTML-)Output einer Instanz zu einer knappen Übergabe für den
    nächsten Agenten in der Kette. Bei Fehler → '' (Aufrufer nutzt dann den Roh-Output)."""
    if not content:
        return ""
    from uuid import uuid4

    from autogen_core.models import UserMessage
    from agent_runtime.executor import ExecutorContext
    from agent_runtime.model_client import make_model_client
    from agent_runtime.spec import AgentSpec

    prompt = (
        f"Hier ist das Ergebnis des Agenten »{source_title}«:\n\n{content}\n\n"
        "Fasse es KNAPP und sachlich auf Deutsch zusammen, sodass der nächste Agent damit "
        "weiterarbeiten kann (Fakten, Ergebnisse, relevante Daten; OHNE HTML/Markup; "
        "max. ~1500 Zeichen). Gib NUR die Zusammenfassung aus, ohne Vorrede."
    )
    spec = AgentSpec(id=uuid4(), name="handoff-summarizer", system_prompt="",
                     model="claude-haiku-4-5", provider="anthropic",
                     api_key=settings.anthropic_api_key)
    ctx = ExecutorContext(api_key=settings.anthropic_api_key, on_event=lambda _e: None,
                          ollama_url=settings.ollama_url)
    client = make_model_client(spec, ctx)
    try:
        res = await client.create([UserMessage(content=prompt, source="user")])
        out = res.content if isinstance(res.content, str) else None
        return (out or "").strip()[:2000]
    except Exception:
        return ""
    finally:
        await client.close()
