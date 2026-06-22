from __future__ import annotations
from app.schemas.agents import AgentCreate


def test_agent_create_defaults_to_cloud_not_local():
    a = AgentCreate(name="X")
    # Default ist ein Cloud-Provider (kein lokales Ollama/qwen mehr).
    assert a.provider in ("deepseek", "anthropic", "openai")
    assert a.provider != "ollama" and "qwen" not in a.model
