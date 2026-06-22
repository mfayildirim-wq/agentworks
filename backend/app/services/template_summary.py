"""Erzeugt aus dem Prompt einer Agent-Vorlage eine knappe Fähigkeits-Beschreibung
(für Marktplatz + späteres Verteiler-Routing). Haiku, Plattform-Key, fail-closed —
Muster wie chat_summary.summarize_output."""
from __future__ import annotations

from app.core.settings import get_settings

settings = get_settings()


async def summarize_prompt(prompt: str) -> str:
    """1–2 knappe Sätze: wofür ist dieser Agent gut / wann nutzt man ihn.
    Bei Fehler/leerem Prompt → '' (Aufrufer lässt description dann unverändert)."""
    if not (prompt or "").strip():
        return ""
    from uuid import uuid4

    from autogen_core.models import UserMessage
    from agent_runtime.executor import ExecutorContext
    from agent_runtime.model_client import make_model_client
    from agent_runtime.spec import AgentSpec

    text = (
        "Hier ist die Aufgaben-/System-Anweisung eines Agenten:\n\n"
        f"{prompt[:6000]}\n\n"
        "Beschreibe in 1–2 KNAPPEN Sätzen auf Deutsch, wofür dieser Agent gut ist und "
        "wann man ihn nutzt (für die spätere automatische Zuordnung eingehender "
        "Nachrichten). Nur die Beschreibung, ohne Vorrede, ohne Markup, max. ~300 Zeichen."
    )
    spec = AgentSpec(id=uuid4(), name="template-summarizer", system_prompt="",
                     model="claude-haiku-4-5", provider="anthropic",
                     api_key=settings.anthropic_api_key)
    ctx = ExecutorContext(api_key=settings.anthropic_api_key, on_event=lambda _e: None,
                          ollama_url=settings.ollama_url)
    client = make_model_client(spec, ctx)
    try:
        res = await client.create([UserMessage(content=text, source="user")])
        out = res.content if isinstance(res.content, str) else None
        return (out or "").strip()[:400]
    except Exception:
        return ""
    finally:
        await client.close()
