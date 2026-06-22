"""Concierge-Router: wählt anhand der Template-Beschreibungen die passende Instanz
(oder fragt nach). Haiku, Plattform-Key; der Aufruf wird dem Nutzer berechnet."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from uuid import UUID

from app.core.settings import get_settings
from app.services import billing

settings = get_settings()


@dataclass
class RouteDecision:
    action: str                     # "use" | "ask"
    artifact_id: UUID | None = None
    candidates: list = field(default_factory=list)   # [{n, artifact_id, title}]


def _ask_all(candidates: list) -> RouteDecision:
    cands = [{"n": i + 1, "artifact_id": c["artifact_id"], "title": c["title"]}
             for i, c in enumerate(candidates)]
    return RouteDecision(action="ask", candidates=cands)


async def route(db, owner_id: UUID, *, message: str, active, candidates: list) -> RouteDecision:
    if not candidates:
        return RouteDecision(action="ask", candidates=[])
    if len(candidates) == 1:
        return RouteDecision(action="use", artifact_id=candidates[0]["artifact_id"])

    from uuid import uuid4

    from autogen_core.models import UserMessage
    from agent_runtime.executor import ExecutorContext
    from agent_runtime.model_client import make_model_client
    from agent_runtime.spec import AgentSpec

    lines = [f"{i+1}) {c['title']} — {c.get('description') or ''}" for i, c in enumerate(candidates)]
    active_line = "keiner"
    for c in candidates:
        if active is not None and str(c["artifact_id"]) == str(active):
            active_line = c["title"]
    prompt = (
        f"Eingehende Nachricht: «{message[:1000]}».\n"
        f"Aktiver Agent: {active_line}.\n"
        "Verfügbare Agenten:\n" + "\n".join(lines) + "\n\n"
        "Wenn der aktive Agent noch passt, behalte ihn. Passt ein anderer KLAR besser "
        "(Themenwechsel), wechsle. Unklar oder mehrere gleich gut → frage.\n"
        'Antworte NUR mit JSON: {"action":"use","n":<Zahl>} ODER {"action":"ask","ns":[<Zahlen>]}.'
    )
    spec = AgentSpec(id=uuid4(), name="router", system_prompt="",
                     model="claude-haiku-4-5", provider="anthropic",
                     api_key=settings.anthropic_api_key)
    ctx = ExecutorContext(api_key=settings.anthropic_api_key, on_event=lambda _e: None,
                          ollama_url=settings.ollama_url)
    cli = make_model_client(spec, ctx)
    raw, tin, tout = "", 0, 0
    try:
        res = await cli.create([UserMessage(content=prompt, source="user")])
        raw = res.content if isinstance(res.content, str) else ""
        u = cli.total_usage()
        tin = int(getattr(u, "prompt_tokens", 0) or 0)
        tout = int(getattr(u, "completion_tokens", 0) or 0)
    except Exception:
        raw = ""
    finally:
        await cli.close()

    try:
        await billing.charge_for_router_turn(db, owner_id=owner_id,
                                             model="claude-haiku-4-5", tokens_in=tin, tokens_out=tout)
    except Exception:
        pass

    try:
        data = json.loads(raw[raw.index("{"):raw.rindex("}") + 1])
        if data.get("action") == "use":
            n = int(data["n"])
            if 1 <= n <= len(candidates):
                return RouteDecision(action="use", artifact_id=candidates[n - 1]["artifact_id"])
        if data.get("action") == "ask":
            ns = [int(x) for x in (data.get("ns") or []) if 1 <= int(x) <= len(candidates)]
            chosen = [candidates[i - 1] for i in ns] or candidates
            return _ask_all(chosen)
    except Exception:
        pass
    return _ask_all(candidates)
