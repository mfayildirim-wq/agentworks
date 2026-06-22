"""Baut je nach Provider den passenden AutoGen-Model-Client.

- anthropic: AnthropicChatCompletionClient
- openai:    OpenAIChatCompletionClient
- ollama:    OpenAIChatCompletionClient gegen die OpenAI-kompatible Ollama-API ({url}/v1)
"""

from __future__ import annotations

from typing import Any

from agent_runtime.executor import ExecutorContext
from agent_runtime.spec import AgentSpec

# Ganze HTML-Seiten brauchen viel Output. Der Default vieler Clients (oft ~1–4k)
# schneidet den ```canvas```-Block mitten in der Seite ab → Zaun schließt nie →
# keine Version. Modell-bewusst, weil die Obergrenzen je Modell variieren.
def _max_tokens_for(model: str) -> int:
    m = (model or "").lower()
    if "haiku" in m:  # konservativ (Haiku-Obergrenze niedriger)
        return 8192
    if "gpt-4o" in m:  # GPT-4o erlaubt max. 16384 Completion-Tokens
        return 16384
    if "deepseek" in m:  # deepseek-chat: max. 8192 Completion-Tokens
        return 8192
    return 16384  # Claude Sonnet/Opus 4.x u.a. — genug für ganze Seiten


def _ollama_model_info() -> Any:
    from autogen_core.models import ModelInfo

    return ModelInfo(
        vision=False,
        function_calling=False,
        json_output=False,
        family="unknown",
        structured_output=False,
    )


def _anthropic_model_info() -> Any:
    """Explizite Capabilities für Claude. Ohne dies rät AutoGen aus dem Modellnamen —
    neue 4.x-Namen (claude-haiku-4-5 …) kennt es nicht und setzt function_calling=False,
    was den AssistantAgent beim Anhängen von Tools mit „model does not support function
    calling" abbrechen lässt. Alle aktuellen Claude-Modelle können Tools + Vision."""
    from autogen_core.models import ModelInfo

    return ModelInfo(
        vision=True,
        function_calling=True,
        json_output=True,
        family="unknown",
        structured_output=True,
    )


def _deepseek_model_info() -> Any:
    """Capabilities für DeepSeek (OpenAI-kompatibel). deepseek-chat kann Function-Calling
    + JSON; kein Vision. Ohne model_info rät AutoGen aus dem Namen → function_calling=False."""
    from autogen_core.models import ModelInfo

    return ModelInfo(
        vision=False,
        function_calling=True,
        json_output=True,
        family="unknown",
        structured_output=False,
    )


def make_model_client(spec: AgentSpec, ctx: ExecutorContext) -> Any:
    provider = (spec.provider or "anthropic").lower()

    if provider == "deepseek":
        # DeepSeek ist OpenAI-kompatibel → OpenAI-Client gegen api.deepseek.com.
        from autogen_ext.models.openai import OpenAIChatCompletionClient

        return OpenAIChatCompletionClient(
            model=spec.model,
            base_url="https://api.deepseek.com/v1",
            api_key=spec.api_key or ctx.api_key or "",
            max_tokens=_max_tokens_for(spec.model),
            model_info=_deepseek_model_info(),
        )

    if provider == "anthropic":
        from autogen_ext.models.anthropic import AnthropicChatCompletionClient

        return AnthropicChatCompletionClient(
            model=spec.model,
            api_key=spec.api_key or ctx.api_key,
            max_tokens=_max_tokens_for(spec.model),
            model_info=_anthropic_model_info(),
        )

    if provider == "openai":
        from autogen_ext.models.openai import OpenAIChatCompletionClient

        return OpenAIChatCompletionClient(
            model=spec.model, api_key=spec.api_key or "", max_tokens=_max_tokens_for(spec.model)
        )

    if provider == "ollama":
        from autogen_ext.models.openai import OpenAIChatCompletionClient

        base = (ctx.ollama_url or "http://localhost:11434").rstrip("/")
        return OpenAIChatCompletionClient(
            model=spec.model,
            base_url=f"{base}/v1",
            api_key="ollama",
            max_tokens=_max_tokens_for(spec.model),
            model_info=_ollama_model_info(),
        )

    raise ValueError(f"unbekannter provider: {provider}")


def provider_supports_tools(provider: str) -> bool:
    """True für Provider mit nativem Function-Calling (Tools). Ollama kann es nicht."""
    return (provider or "").lower() in ("anthropic", "openai", "deepseek")


def provider_supports_vision(provider: str) -> bool:
    """True für Provider, deren Modelle Bilder verarbeiten (Vision). Ollama (lokal) nicht."""
    return (provider or "").lower() in ("anthropic", "openai")
