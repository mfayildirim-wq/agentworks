import uuid

import pytest

from agent_runtime.executor import ExecutorContext
from agent_runtime.model_client import make_model_client, provider_supports_vision
from agent_runtime.spec import AgentSpec


def _spec(provider: str, model: str, api_key=None) -> AgentSpec:
    return AgentSpec(
        id=uuid.uuid4(),
        name="x",
        system_prompt="y",
        provider=provider,
        model=model,
        api_key=api_key,
    )


def _ctx(ollama_url=None) -> ExecutorContext:
    return ExecutorContext(api_key="global-key", on_event=lambda e: None, ollama_url=ollama_url)


def test_anthropic_client():
    c = make_model_client(_spec("anthropic", "claude-sonnet-4-6", "sk-ant-x"), _ctx())
    from autogen_ext.models.anthropic import AnthropicChatCompletionClient

    assert isinstance(c, AnthropicChatCompletionClient)


def test_openai_client():
    c = make_model_client(_spec("openai", "gpt-4o", "sk-oai-x"), _ctx())
    from autogen_ext.models.openai import OpenAIChatCompletionClient

    assert isinstance(c, OpenAIChatCompletionClient)


def test_ollama_uses_openai_compatible_base_url():
    c = make_model_client(
        _spec("ollama", "qwen2.5:3b"), _ctx(ollama_url="http://172.17.0.1:11434")
    )
    from autogen_ext.models.openai import OpenAIChatCompletionClient

    assert isinstance(c, OpenAIChatCompletionClient)


def test_unknown_provider_raises():
    with pytest.raises(ValueError):
        make_model_client(_spec("mistral-local", "x"), _ctx())


def test_anthropic_supports_vision():
    assert provider_supports_vision("anthropic") is True


def test_openai_supports_vision():
    assert provider_supports_vision("openai") is True


def test_ollama_no_vision():
    assert provider_supports_vision("ollama") is False


def test_unknown_no_vision():
    assert provider_supports_vision("") is False


def test_anthropic_client_reports_function_calling_and_vision():
    # Regression: neue Claude-4.x-Namen würden ohne explizites model_info als
    # tool-unfähig gelten und den AssistantAgent beim Tool-Anhängen abbrechen lassen.
    c = make_model_client(_spec("anthropic", "claude-haiku-4-5", "sk-ant-x"), _ctx())
    assert c.model_info["function_calling"] is True
    assert c.model_info["vision"] is True
